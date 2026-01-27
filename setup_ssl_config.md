# SSL Certificate Setup Instructions

## Steps to configure your CA certificate:

1. **Place your certificate file**: Copy your `ca.cert.pem` file to the root directory of your project (same level as `app.py`)

2. **Create your config.yaml**: Copy `config.yaml.example` to `config.yaml` and update it with your actual values:

```bash
cp config.yaml.example config.yaml
```

3. **Update the SSL section in config.yaml**:
```yaml
ai_model:
  client_id: your_actual_client_id
  client_secret: your_actual_client_secret  
  base_url: your_actual_base_url
  model_name: llama-3-3-70b-instruct
  
  # SSL Configuration for corporate networks
  ssl:
    verify: true                    # Enable SSL verification
    ca_bundle: ca.cert.pem         # Path to your CA certificate file
```

## Alternative SSL configurations:

### Option 1: Use your CA certificate (Recommended)
```yaml
ssl:
  verify: true
  ca_bundle: ca.cert.pem
```

### Option 2: Disable SSL verification (NOT recommended for production)
```yaml
ssl:
  verify: false
```

### Option 3: Use system CA bundle + your certificate
If you need to combine your certificate with the system's CA bundle:
```bash
# Create a combined certificate bundle
cat ca.cert.pem >> combined_ca_bundle.pem
cat /etc/ssl/certs/ca-certificates.crt >> combined_ca_bundle.pem
```

Then use:
```yaml
ssl:
  verify: true
  ca_bundle: combined_ca_bundle.pem
```

## Testing the configuration:

After setting up, test your configuration:
```bash
python3 -c "
from nl2sql.config.manager import Config_Manager
from nl2sql.llm.converter import Query_Converter

config = Config_Manager()
config.load_config()
converter = Query_Converter(config.ai_model_config)
print('SSL configuration loaded successfully!')
"
```