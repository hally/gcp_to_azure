import os, datetime as dt, logging, time, json, re, traceback, base64
from flask import Flask, request, jsonify
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from azure.storage.blob import BlobServiceClient
from azure.data.tables import TableServiceClient
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import AzureOpenAI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s',
    handlers=[logging.StreamHandler()]
)

# Environment variables
SUBSCRIPTION_ID = os.environ["SUBSCRIPTION_ID"]
RESOURCE_GROUP = os.environ["RESOURCE_GROUP"]
SYNAPSE_WORKSPACE = os.environ["SYNAPSE_WORKSPACE"]
SQL_POOL = os.environ["SQL_POOL"]
DATABASE = os.environ["DATABASE"]
RAW_TABLE = os.environ["RAW_TABLE"]
TRANSCRIPT_TABLE = os.environ["TRANSCRIPT_TABLE"]
AZURE_OPENAI_ENDPOINT = os.environ["AZURE_OPENAI_ENDPOINT"]
AZURE_OPENAI_KEY = os.environ["AZURE_OPENAI_KEY"]
AZURE_OPENAI_DEPLOYMENT = os.environ["AZURE_OPENAI_DEPLOYMENT"]
PROMPT_BLOB_URI = os.environ["PROMPT_BLOB_URI"]
PROCESSED_LEDGER = os.environ["PROCESSED_LEDGER"]
CALL_EXTRACTIONS = os.environ["CALL_EXTRACTIONS"]
TOPIC_MODELS = os.environ["TOPIC_MODELS"]
LOBS = os.environ["LOB"]
LIKE_PATTERN = os.environ["LIKE_PATTERN"]
STORAGE_ACCOUNT = os.environ["STORAGE_ACCOUNT"]
KEY_VAULT_URL = os.environ["KEY_VAULT_URL"]

# Initialize Azure clients
credential = DefaultAzureCredential()

# Azure OpenAI client
openai_client = AzureOpenAI(
    api_key=AZURE_OPENAI_KEY,
    api_version="2024-02-01",
    azure_endpoint=AZURE_OPENAI_ENDPOINT
)

# Blob Storage client
blob_service_client = BlobServiceClient(
    account_url=f"https://{STORAGE_ACCOUNT}.blob.core.windows.net",
    credential=credential
)

# Synapse Analytics connection (using pyodbc)
import pyodbc

def get_synapse_connection():
    """Create Synapse SQL connection"""
    connection_string = (
        f"Driver={{ODBC Driver 18 for SQL Server}};"
        f"Server=tcp:{SYNAPSE_WORKSPACE}.sql.azuresynapse.net,1433;"
        f"Database={DATABASE};"
        f"Authentication=ActiveDirectoryMsi;"
        f"Encrypt=yes;"
        f"TrustServerCertificate=no;"
    )
    return pyodbc.connect(connection_string)

fetch_lock = threading.Lock()

# ========== HELPER FUNCTIONS (ADAPTED FOR AZURE) ==========

def fetch_batch_transcripts(batch_size: int, start_date=None, end_date=None):
    """
    Fetch MULTIPLE unprocessed transcripts from Synapse Analytics.
    
    Args:
        batch_size: Number of records to fetch
        start_date: Optional start date
        end_date: Optional end date
    
    Returns:
        List of transcript dicts
    """
    # Date filter logic
    if start_date is None and end_date is None:
        date_filter = "t.call_convrstn_utc_dt = DATEADD(day, -1, CAST(GETDATE() AS DATE))"
        raw_filter = "CAST(r.ts AS DATE) = DATEADD(day, -1, CAST(GETDATE() AS DATE))"
    elif start_date and end_date:
        date_filter = f"t.call_convrstn_utc_dt BETWEEN '{start_date}' AND '{end_date}'"
        raw_filter = f"CAST(r.ts AS DATE) BETWEEN '{start_date}' AND '{end_date}'"
    elif start_date:
        date_filter = f"t.call_convrstn_utc_dt >= '{start_date}'"
        raw_filter = f"CAST(r.ts AS DATE) >= '{start_date}'"
    elif end_date:
        date_filter = f"t.call_convrstn_utc_dt <= '{end_date}'"
        raw_filter = f"CAST(r.ts AS DATE) <= '{end_date}'"

    query = f"""
      SELECT TOP {batch_size}
        t.call_convrstn_id       AS call_id,
        CAST(t.cust_id AS NVARCHAR(255)) AS cust_id,
        t.lob AS lob,
        t.insights_transcript_txt AS transcript_text
      FROM {TRANSCRIPT_TABLE} t
      LEFT JOIN {RAW_TABLE} r
        ON t.call_convrstn_id = r.call_convrstn_id
        AND {raw_filter}
      WHERE r.call_convrstn_id IS NULL
        AND t.topicmodel IN {TOPIC_MODELS}
        AND t.lob IN {LOBS}
        AND t.insights_transcript_txt LIKE '{LIKE_PATTERN}'
        AND {date_filter}
        AND LEN(TRIM(insights_transcript_txt)) - LEN(REPLACE(TRIM(insights_transcript_txt), ' ', '')) + 1 >= 20
    """
    
    results = []
    conn = get_synapse_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(query)
        for row in cursor.fetchall():
            results.append({
                "call_id": row.call_id,
                "cust_id": row.cust_id,
                "lob": row.lob,
                "transcript_text": row.transcript_text
            })
    finally:
        cursor.close()
        conn.close()
    
    logging.info(f"📦 Fetched {len(results)} records from Synapse")
    return results

def read_prompt_text() -> str:
    """Read prompt from Azure Blob Storage"""
    # Parse blob URI: https://storageaccount.blob.core.windows.net/container/path/to/file.txt
    blob_uri = PROMPT_BLOB_URI.replace("https://", "").replace(f"{STORAGE_ACCOUNT}.blob.core.windows.net/", "")
    container_name, blob_path = blob_uri.split("/", 1)
    
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_path)
    return blob_client.download_blob().readall().decode('utf-8')

def call_azure_openai(prompt_text: str, transcript_text: str):
    """Call Azure OpenAI"""
    prompt = f"{prompt_text}\n\n=== TRANSCRIPT START ===\n{transcript_text}\n=== TRANSCRIPT END ==="
    
    response = openai_client.chat.completions.create(
        model=AZURE_OPENAI_DEPLOYMENT,
        messages=[
            {"role": "system", "content": "You are an expert at analyzing customer service call transcripts."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.1,
        max_tokens=4000
    )
    
    return response.choices[0].message.content

def parse_openai_output(openai_text):
    """
    Extract and parse JSON from Azure OpenAI response.
    Removes markdown code blocks and extra text after JSON.
    """
    try:
        cleaned = openai_text.strip()
        
        # Remove markdown code blocks
        cleaned = re.sub(r'^```(?:json)?\s*\n', '', cleaned)
        cleaned = re.sub(r'\n```\s*$', '', cleaned)
        
        # Find JSON boundaries
        first_brace = cleaned.find('{')
        last_brace = cleaned.rfind('}')
        
        if first_brace == -1 or last_brace == -1:
            logging.error(f"❌ No JSON object found in response")
            return None
        
        # Extract only the JSON part
        json_only = cleaned[first_brace:last_brace + 1]
        
        # Parse it
        parsed = json.loads(json_only)
        logging.info(f"✅ Successfully parsed OpenAI output")
        return parsed
        
    except json.JSONDecodeError as e:
        logging.error(f"❌ JSON parse error: {e}")
        logging.error(f"Raw output (first 500 chars): {openai_text[:500]}...")
        logging.error(f"Raw output (last 200 chars): ...{openai_text[-200:]}")
        return None
        
    except Exception as e:
        logging.error(f"❌ Unexpected parsing error: {e}")
        return None

def safe_string(value):
    """Convert value to string, handling arrays and None"""
    if value is None:
        return None
    if isinstance(value, list):
        return " | ".join(str(v) for v in value if v is not None)
    return str(value)

def get_field_safe(data, *possible_names):
    """Try multiple field names (handles case variations)"""
    for name in possible_names:
        if name in data:
            return data[name]
    for name in possible_names:
        lowercase_name = name.lower()
        if lowercase_name in data:
            return data[lowercase_name]
    return None

def safe_integer(value):
    """Convert value to integer, handling non-numeric values"""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        value = value.strip().upper()
        if "[ALL_ALPHANUMERIC_SPECIAL_CHARACTERS]" in value:
            return None
        if value in ["N/A", "NA", "NULL", "NONE", "NOT APPLICABLE", "ONGOING", "UNKNOWN", ""]:
            return None
        try:
            return int(value)
        except ValueError:
            logging.warning(f"⚠️ Could not convert '{value}' to integer")
            return None
    if isinstance(value, float):
        return int(value)
    return None

def safe_float(value):
    """Convert value to float, handling non-numeric values"""
    if value is None:
        return None
    if isinstance(value, (float, int)):
        return float(value)
    if isinstance(value, str):
        value = value.strip().upper()
        if "[ALL_ALPHANUMERIC_SPECIAL_CHARACTERS]" in value:
            return None
        if value in ["N/A", "NA", "NULL", "NONE", "NOT APPLICABLE", "UNKNOWN", ""]:
            return None
        try:
            return float(value)
        except ValueError:
            logging.warning(f"⚠️ Could not convert '{value}' to float")
            return None
    return None

def build_tags_dict(tags_data):
    """Build tags dict, omitting empty arrays"""
    tags_dict = {}
    
    customer_intent = tags_data.get("customer_intent_tags")
    if customer_intent and isinstance(customer_intent, list) and len(customer_intent) > 0:
        tags_dict["customer_intent_tags"] = customer_intent
    
    agent = tags_data.get("agent_tags")
    if agent and isinstance(agent, list) and len(agent) > 0:
        tags_dict["agent_tags"] = agent
    
    operational = tags_data.get("operational_tags")
    if operational and isinstance(operational, list) and len(operational) > 0:
        tags_dict["operational_tags"] = operational
    
    return tags_dict

def parse_financial_summary(financial_data):
    """Parse financial summary into structured format"""
    if financial_data is None:
        return []
    
    financial_records = []
    
    # Parse incident context
    incident_context = financial_data.get("incident_context") or {}
    disputed_amount = incident_context.get("disputed_amount") or {}
    
    if disputed_amount and disputed_amount.get("value") is not None:
        financial_records.append({
            "tag": "disputed_amount",
            "amount": safe_float(disputed_amount.get("value")),
            "currency": "CAD",
            "impact_type": disputed_amount.get("type", "Unspecified"),
            "duration_months": None,
            "description": disputed_amount.get("description"),
        })
    
    # Parse resolution offers
    for offer in financial_data.get("resolution_offers", []):
        offer_details = offer.get("offer_details") or {}
        financial_records.append({
            "tag": offer_details.get("tag"),
            "amount": safe_float(offer_details.get("monthly_impact")),
            "currency": "CAD",
            "impact_type": "resolution_offer",
            "duration_months": safe_integer(offer_details.get("duration_months")),
            "description": offer_details.get("description"),
        })
    
    # Parse MRR impacts
    for impact in financial_data.get("mrr_impacts", []):
        financial_records.append({
            "tag": impact.get("tag"),
            "amount": safe_float(impact.get("monthly_impact")),
            "currency": "CAD",
            "impact_type": "mrr_impact",
            "duration_months": safe_integer(impact.get("duration_months")),
            "description": impact.get("description"),
        })
    
    # Parse one-time impacts
    for impact in financial_data.get("one_time_impacts", []):
        financial_records.append({
            "tag": impact.get("tag"),
            "amount": safe_float(impact.get("amount")),
            "currency": "CAD",
            "impact_type": "one_time_impact",
            "duration_months": None,
            "description": impact.get("description"),
        })
    
    # Parse administrative actions
    for action in financial_data.get("administrative_actions", []):
        financial_records.append({
            "tag": action.get("tag"),
            "amount": safe_float(action.get("amount")),
            "currency": "CAD",
            "impact_type": "administrative_action",
            "duration_months": safe_integer(action.get("duration_months")),
            "description": action.get("description"),
        })
    
    return financial_records

def insert_call_extraction(call_id, cust_id, lob, parsed_data):
    """Insert parsed output into Synapse Analytics"""
    try:
        structured_summary_data = parsed_data.get("structured_summary") or {}
        financial_summary_data = parsed_data.get("financial_summary") or {}
        tags_data = parsed_data.get("tags") or {}
        scores_data = parsed_data.get("scores") or {}
        
        # Convert complex objects to JSON strings for Synapse
        structured_summary_json = json.dumps({
            "Customer_Intent": safe_string(get_field_safe(structured_summary_data, "Customer_Intent", "customer_intent")),
            "Agent_Resolution_Steps": safe_string(get_field_safe(structured_summary_data, "Agent_Resolution_Steps", "agent_resolution_steps")),
            "Root_Cause": safe_string(get_field_safe(structured_summary_data, "Root_Cause", "root_cause")),
            "Final_Call_Resolution": safe_string(get_field_safe(structured_summary_data, "Resolution_Description", "resolution_description", "Resolution_Status")),
        })
        
        financial_summary_json = json.dumps(parse_financial_summary(financial_summary_data))
        tags_json = json.dumps(build_tags_dict(tags_data))
        scores_json = json.dumps({
            "Customer_Effort_Score": scores_data.get("Customer_Effort_Score"),
            "Issue_Resolution_Score": scores_data.get("Issue_Resolution_Score"),
            "Revenue_Impact_Score": scores_data.get("Revenue_Impact_Score"),
            "Escalation_Risk_Score": scores_data.get("Escalation_Risk_Score"),
            "Agent_Effectiveness_Score": scores_data.get("Agent_Effectiveness_Score"),
        })
        
        channel_journey_json = json.dumps([json.dumps(journey) for journey in parsed_data.get("channel_journey", [])])
        
        # Insert into Synapse
        conn = get_synapse_connection()
        cursor = conn.cursor()
        
        insert_query = f"""
        INSERT INTO {CALL_EXTRACTIONS} (
            call_convrstn_id, cust_id, lob, interaction_type, incident_classification,
            failure_origin_channel, channel_journey, structured_summary, financial_summary,
            tags, scores, parsed_on
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        cursor.execute(insert_query, (
            call_id,
            cust_id,
            lob,
            parsed_data.get("interaction_type"),
            parsed_data.get("incident_classification"),
            parsed_data.get("failure_origin_channel"),
            channel_journey_json,
            structured_summary_json,
            financial_summary_json,
            tags_json,
            scores_json,
            dt.datetime.utcnow().isoformat()
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logging.info(f"✅ Inserted call_id {call_id} into Synapse")
        
    except Exception as e:
        logging.error(f"❌ Failed to insert call_extraction for {call_id}: {e}")
        logging.error(f"Full traceback: {traceback.format_exc()}")
        raise

def insert_processed_ledger(workflow_execution_id, batch_number, processed_count, failed_count, duration_seconds, status):
    """Insert completion record into processed_ledger table"""
    try:
        conn = get_synapse_connection()
        cursor = conn.cursor()
        
        insert_query = f"""
        INSERT INTO {PROCESSED_LEDGER} (
            workflow_execution_id, batch_number, processed_count, failed_count,
            duration_seconds, status, processed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        
        cursor.execute(insert_query, (
            workflow_execution_id,
            batch_number,
            processed_count,
            failed_count,
            round(duration_seconds, 2),
            status,
            dt.datetime.utcnow().isoformat()
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logging.info(f"✅ Inserted processed_ledger for workflow {workflow_execution_id}, batch {batch_number}")
        
    except Exception as e:
        logging.error(f"❌ Error inserting processed_ledger: {e}")

def ensure_raw_table_exists():
    """Create raw table if it doesn't exist in Synapse"""
    conn = get_synapse_connection()
    cursor = conn.cursor()
    
    create_table_sql = f"""
    IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = '{RAW_TABLE}')
    BEGIN
        CREATE TABLE {RAW_TABLE} (
            call_convrstn_id NVARCHAR(255),
            cust_id NVARCHAR(255),
            model_output NVARCHAR(MAX),
            model_name NVARCHAR(255),
            ts DATETIME2
        )
    END
    """
    
    cursor.execute(create_table_sql)
    conn.commit()
    cursor.close()
    conn.close()
    
    logging.info("✅ Ensured raw table exists in Synapse")

def insert_raw_output(call_id: str, cust_id: str, openai_text: str):
    """Insert raw Azure OpenAI output into Synapse"""
    try:
        conn = get_synapse_connection()
        cursor = conn.cursor()
        
        insert_query = f"""
        INSERT INTO {RAW_TABLE} (call_convrstn_id, cust_id, model_output, model_name, ts)
        VALUES (?, ?, ?, ?, ?)
        """
        
        cursor.execute(insert_query, (
            call_id,
            cust_id,
            openai_text,
            AZURE_OPENAI_DEPLOYMENT,
            dt.datetime.utcnow()
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logging.info(f"✅ Inserted raw output for {call_id}")
        
    except Exception as e:
        logging.error(f"❌ Error inserting raw output: {e}")

# ========== CORE PROCESSING LOGIC ==========

def process_single_record(prompt_text: str, transcript: dict):
    """Process ONE pre-fetched record"""
    try:
        call_id = transcript["call_id"]
        cust_id = transcript.get("cust_id")
        lob = transcript.get("lob")
        transcript_text = transcript["transcript_text"]
        
        # Call Azure OpenAI
        openai_text = call_azure_openai(prompt_text, transcript_text)
        
        # Save raw output
        insert_raw_output(call_id, cust_id, openai_text)
        
        # Parse and insert structured data
        parsed_output = parse_openai_output(openai_text)
        
        if not parsed_output:
            logging.error(f"❌ Failed to parse output for {call_id}")
            return {"status": "failed", "call_id": call_id}
        
        insert_call_extraction(call_id, cust_id, lob, parsed_output)
        
        return {"status": "success", "call_id": call_id}
        
    except Exception as e:
        logging.error(f"❌ Error processing record: {e}")
        return {"status": "failed"}

def process_batch_parallel(trace_id: str, max_workers: int = 30, max_records: int = 100, 
                          chunk_size: int = 50, start_date=None, end_date=None):
    """Process records in parallel"""
    start_time = time.time()
    prompt_text = read_prompt_text()
    
    processed_count = 0
    failed_count = 0
    consecutive_empty_batches = 0
    
    logging.info(
        f"🚀 BATCH MODE | "
        f"Workers: {max_workers} | "
        f"Max records: {max_records} | "
        f"Chunk size: {chunk_size} | "
        f"Date range: {start_date or 'yesterday'} to {end_date or 'yesterday'} | "
        f"TraceID: {trace_id}"
    )
    
    while processed_count + failed_count < max_records:
        remaining = max_records - (processed_count + failed_count)
        current_chunk_size = min(chunk_size, remaining)

        with fetch_lock:
            logging.info(f"📦 Fetching {current_chunk_size} records from Synapse...")
            transcripts = fetch_batch_transcripts(current_chunk_size, start_date, end_date)
            
            if not transcripts:
                consecutive_empty_batches += 1
                if consecutive_empty_batches >= 3:
                    logging.info("✅ No more records available")
                    break
                continue
            
            consecutive_empty_batches = 0
            
            logging.info(f"📦 Processing {len(transcripts)} records in parallel...")
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(process_single_record, prompt_text, transcript) 
                          for transcript in transcripts]
                
                chunk_processed = 0
                chunk_failed = 0
                
                for future in as_completed(futures):
                    result = future.result()
                    
                    if result["status"] == "success":
                        chunk_processed += 1
                    elif result["status"] == "failed":
                        chunk_failed += 1
                
                processed_count += chunk_processed
                failed_count += chunk_failed

                logging.info(
                    f"✅ Chunk complete | "
                    f"Processed: {chunk_processed} | "
                    f"Failed: {chunk_failed} | "
                    f"Total: {processed_count}/{max_records}"
                )
            
            logging.info(f"⏳ Waiting 5 seconds for Synapse visibility...")
            time.sleep(5)
    
    total_time = time.time() - start_time
    rate = processed_count / total_time if total_time > 0 else 0
    
    logging.info(
        f"✅ BATCH COMPLETE | "
        f"Processed: {processed_count:,} | "
        f"Failed: {failed_count} | "
        f"Time: {total_time/60:.1f} min | "
        f"Rate: {rate:.1f} rec/sec"
    )
    
    insert_processed_ledger(
        workflow_execution_id=trace_id,
        batch_number=0,
        processed_count=processed_count,
        failed_count=failed_count,
        duration_seconds=total_time,
        status="COMPLETED"
    )
    
    return {
        "processed_count": processed_count,
        "failed_count": failed_count,
        "duration_minutes": round(total_time / 60, 2),
        "rate_per_second": round(rate, 2)
    }

# ========== FLASK APP ==========

app = Flask(__name__)

@app.route("/", methods=["GET"])
def index():
    return "Azure Echo OpenAI Synapse Service - Ready", 200

@app.route("/healthz", methods=["GET"])
def healthz():
    return "ok", 200

@app.route("/process", methods=["POST"])
def process_batch():
    """HTTP endpoint for batch processing"""
    try:
        payload = request.get_json(force=True)
        trace_id = payload.get("traceId", "unknown")
        max_records = payload.get("maxRecords", 100)
        chunk_size = payload.get("chunkSize", 50)
        max_workers = payload.get("maxWorkers", 30)
        start_date = payload.get("startDate")
        end_date = payload.get("endDate")
        
        logging.info(
            f"📥 Received batch request | "
            f"TraceID: {trace_id} | "
            f"Total records: {max_records} | "
            f"Chunk size: {chunk_size} | "
            f"Workers: {max_workers} | "
            f"Date range: {start_date or 'yesterday'} to {end_date or 'yesterday'}"
        )

        ensure_raw_table_exists()
        
        def process_in_background():
            try:
                result = process_batch_parallel(trace_id, max_workers, max_records, chunk_size, start_date, end_date)
                logging.info(f"✅ Background processing complete - {result}")
            except Exception as e:
                logging.error(f"❌ Background processing failed - {e}")
        
        thread = threading.Thread(target=process_in_background, daemon=True)
        thread.start()
        
        return jsonify({
            "ok": True,
            "status": "started",
            "trace_id": trace_id,
            "max_records": max_records,
            "start_date": start_date or "yesterday",
            "end_date": end_date or "yesterday",
            "message": "Processing started in background"
        }), 200
        
    except Exception as e:
        logging.exception("❌ Fatal error in /process endpoint")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
