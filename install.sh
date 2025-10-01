#!/bin/bash

# Colors used for messages
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Message display functions
print_message() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Important paths
BOT_PATH="/root/DLBot"
BOT_SERVICE="/etc/systemd/system/dlbot.service"

# Check for root privileges
if [ "$EUID" -ne 0 ]; then
    print_error "This script must be run with root privileges!"
    print_warning "Please run with sudo"
    exit 1
fi

# Update package list
print_message "Updating package list..."
apt update

# Install essential prerequisites
print_message "Installing system prerequisites..."
apt install -y python3 python3-pip python3-venv nginx socat curl wget git

# Clone repository from GitHub
print_message "Cloning repository from GitHub..."
TEMP_DIR="/tmp/telegram-bot-temp"
rm -rf "$TEMP_DIR"  # Clean up any previous temporary directory

if [ -d "$BOT_PATH" ]; then
    print_warning "Directory $BOT_PATH already exists, updating..."
    cd "$BOT_PATH"
    git pull origin master || print_warning "Failed to update repository"
else
    # Clone to temporary directory first
    git clone https://github.com/ArashAfkandeh/Telegram-File-to-Link.git "$TEMP_DIR" || {
        print_error "Failed to clone repository"
        exit 1
    }
    
    # Create bot directory
    mkdir -p "$BOT_PATH"
    
    # Move all files from temp directory to bot directory
    mv "$TEMP_DIR"/* "$BOT_PATH"/ || {
        print_error "Failed to move files"
        exit 1
    }
    
    # Clean up temporary directory
    rm -rf "$TEMP_DIR"
    print_message "Repository files moved to $BOT_PATH successfully"
fi

# Install or update required Python packages
print_message "Installing Python libraries..."
python3 -m pip install --upgrade pip
python3 -m pip install pyrogram tgcrypto psutil uvloop

# Create required directories
print_message "Creating required directories..."
mkdir -p /var/www/html/dl
chown -R www-data:www-data /var/www/html
chmod -R 755 /var/www/html

# Get domain and email
if [ -z "$1" ]; then
    read -p "🌐 Please enter domain name: " HOST
else
    HOST="$1"
fi

if [ -z "$2" ]; then
    read -p "📧 Please enter email address: " EMAIL
    while [ -z "$EMAIL" ]; do
        print_error "Email cannot be empty"
        read -p "📧 Please enter email address: " EMAIL
    done
else
    EMAIL="$2"
fi

# SSL variables
CERT_DIR="/root/cert/$HOST"
KEY_FILE="$CERT_DIR/privkey.pem"
CHAIN_FILE="$CERT_DIR/fullchain.pem"

# Set up temporary nginx config for ACME challenge
print_message "Configuring nginx for domain ownership verification..."
cat > /etc/nginx/sites-available/dlbot << EOL
server {
    listen 80;
    listen [::]:80;
    server_name $HOST;
    
    location ^~ /.well-known/acme-challenge/ {
        default_type "text/plain";
        root /var/www/html;
    }
    
    location / {
        return 301 https://\$host\$request_uri;
    }
}
EOL

# Enable temporary configuration
ln -sf /etc/nginx/sites-available/dlbot /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

# Install acme.sh if not already installed
if [ ! -d "$HOME/.acme.sh" ]; then
    print_message "Installing acme.sh..."
    curl https://get.acme.sh | sh
    source ~/.bashrc
fi

# Set CA to Let's Encrypt
~/.acme.sh/acme.sh --set-default-ca --server letsencrypt

# Function to check if certificate renewal is needed
need_renewal() {
    [ ! -f "$KEY_FILE" ] || [ ! -f "$CHAIN_FILE" ] && return 0
    EXP=$(openssl x509 -enddate -noout -in "$CHAIN_FILE" | cut -d= -f2)
    EXP_TS=$(date -d "$EXP" +%s)
    THRESHOLD=$(( $(date +%s) + 60*24*3600 ))
    [ "$EXP_TS" -le "$THRESHOLD" ]
}

# Issue or renew if needed
if need_renewal; then
    print_message "Issuing/renewing SSL certificate for $HOST..."
    ~/.acme.sh/acme.sh --issue -d "$HOST" --webroot /var/www/html --accountemail "$EMAIL"
else
    print_message "Certificate valid for >7 days, no renewal needed."
fi

# Create certificate installation path if it doesn't exist
if [ ! -d "$CERT_DIR" ]; then
    mkdir -p "$CERT_DIR"
fi

# Install certificate if newly issued
if need_renewal; then
    print_message "Installing certificate in $CERT_DIR..."
    ~/.acme.sh/acme.sh --install-cert -d "$HOST" \
        --key-file "$KEY_FILE" \
        --fullchain-file "$CHAIN_FILE"
fi

# Enable auto-upgrade
~/.acme.sh/acme.sh --upgrade --auto-upgrade

# Weekly cronjob (Sunday 00:00)
(crontab -l 2>/dev/null; echo "0 0 * * 0 ~/.acme.sh/acme.sh --cron --home ~/.acme.sh > /dev/null") | sort -u | crontab -

# Configure nginx
print_message "Configuring nginx with SSL..."
cat > /etc/nginx/sites-available/dlbot << EOL
server {
    listen 80;
    listen [::]:80;
    server_name $HOST;
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name $HOST;

    ssl_certificate $CHAIN_FILE;
    ssl_certificate_key $KEY_FILE;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:50m;
    ssl_stapling on;
    ssl_stapling_verify on;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    root /var/www/html;
    index index.html;

    location /dl/ {
        alias /var/www/html/dl/;
        autoindex off;
        try_files \$uri \$uri/ =404;
    }

    location / {
        try_files \$uri \$uri/ =404;
    }
}
EOL

# Enable nginx configuration
ln -sf /etc/nginx/sites-available/dlbot /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Check nginx configuration
nginx -t

if [ $? -eq 0 ]; then
    # Restart nginx
    systemctl restart nginx
    print_message "nginx configured and restarted successfully"
else
    print_error "Error in nginx configuration!"
    exit 1
fi

# Configure firewall (if ufw is installed)
if command -v ufw >/dev/null 2>&1; then
    print_message "Configuring firewall..."
    ufw status | grep -q "Status: active" && {
        ufw allow 'Nginx Full'
        ufw allow 22/tcp
        print_message "Firewall rules added"
    } || print_warning "ufw firewall is not active"
else
    print_warning "ufw firewall is not installed, no configuration needed"
fi

# Create systemd service
print_message "Creating systemd service for the bot..."
cat > /etc/systemd/system/telegrambot.service << 'EOL'
[Unit]
Description=Telegram File Saver Bot
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/html/bot
ExecStart=/usr/bin/python3 /var/www/html/bot/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOL

# Get user settings and create config.json
print_message "Setting up bot configuration..."

# Function to validate api_id (must be a number)
validate_api_id() {
    local value="$1"
    if [[ ! "$value" =~ ^[0-9]+$ ]]; then
        return 1
    fi
    return 0
}

# Function to validate api_hash (must be a 32-character hexadecimal)
validate_api_hash() {
    local value="$1"
    if [[ ! "$value" =~ ^[a-fA-F0-9]{32}$ ]]; then
        return 1
    fi
    return 0
}

# Function to validate bot_token (must match the correct pattern)
validate_bot_token() {
    local value="$1"
    if [[ ! "$value" =~ ^[0-9]+:[A-Za-z0-9_-]{35}$ ]]; then
        return 1
    fi
    return 0
}

# Get api_id with validation
while true; do
    read -p "🔑 Please enter Telegram api_id: " API_ID
    if [ -z "$API_ID" ]; then
        print_error "api_id cannot be empty"
        continue
    fi
    if ! validate_api_id "$API_ID"; then
        print_error "api_id must be an integer"
        continue
    fi
    break
done

# Get api_hash with validation
while true; do
    read -p "🔑 Please enter Telegram api_hash: " API_HASH
    if [ -z "$API_HASH" ]; then
        print_error "api_hash cannot be empty"
        continue
    fi
    if ! validate_api_hash "$API_HASH"; then
        print_error "api_hash must be a 32-character hexadecimal string"
        continue
    fi
    break
done

# Get bot_token with validation
while true; do
    read -p "🤖 Please enter bot token: " BOT_TOKEN
    if [ -z "$BOT_TOKEN" ]; then
        print_error "Bot token cannot be empty"
        continue
    fi
    if ! validate_bot_token "$BOT_TOKEN"; then
        print_error "Invalid bot token format"
        continue
    fi
    break
done

# Get allowed user IDs
read -p "👥 Enter allowed user IDs (comma-separated or Enter for public access): " ALLOWED_USERS
if [ -z "$ALLOWED_USERS" ]; then
    ALLOWED_JSON="[]"
    print_message "Access enabled for all users"
else
    IFS=',' read -ra ALLOWED_ARRAY <<< "$ALLOWED_USERS"
    ALLOWED_JSON="["
    for i in "${!ALLOWED_ARRAY[@]}"; do
        ALLOWED_JSON+="${ALLOWED_ARRAY[i]}"
        if [ $i -lt $((${#ALLOWED_ARRAY[@]}-1)) ]; then
            ALLOWED_JSON+=","
        fi
    done
    ALLOWED_JSON+="]"
    print_message "Access configured for ${#ALLOWED_ARRAY[@]} users"
fi

# Get maximum file age
read -p "⏳ Maximum file age in hours (Enter = 24): " MAX_AGE
if [ -z "$MAX_AGE" ]; then
    MAX_AGE=24
    print_message "Default value of 24 hours set"
fi

# Function to check Telegram connectivity
check_telegram_connection() {
    local timeout=5
    print_message "Checking connection to Telegram..."
    
    # Test multiple Telegram domains
    local domains=(
        "api.telegram.org"
        "core.telegram.org"
        "telegram.me"
    )
    
    for domain in "${domains[@]}"; do
        if curl --connect-timeout $timeout -s "https://$domain" >/dev/null 2>&1; then
            return 0
        fi
    done
    return 1
}

# Check if proxy is needed
if check_telegram_connection; then
    print_message "Connection to Telegram is working, no proxy needed"
    USE_PROXY="n"
else
    print_warning "Unable to connect to Telegram"
    while true; do
        read -p "🌐 Would you like to configure a proxy? (y/N): " USE_PROXY_INPUT
        case $USE_PROXY_INPUT in
            [Yy]* )
                USE_PROXY="y"
                break
                ;;
            [Nn]* | "" )
                print_warning "Continuing without proxy, bot may not work"
                USE_PROXY="n"
                break
                ;;
            * )
                print_error "Please enter y or n"
                ;;
        esac
    done
fi
if [[ $USE_PROXY =~ ^[Yy]$ ]]; then
    # Proxy settings as required values
    while true; do
        read -p "🔧 Enter proxy type (Enter = socks5): " PROXY_SCHEME
        if [ -z "$PROXY_SCHEME" ]; then
            PROXY_SCHEME="socks5"
            print_message "Proxy type set to socks5"
        fi
        
        read -p "🖥️ Enter proxy server address: " PROXY_SERVER
        if [ -z "$PROXY_SERVER" ]; then
            print_error "Proxy address cannot be empty"
            continue
        fi
        
        read -p "🔌 Enter proxy port: " PROXY_PORT
        if [ -z "$PROXY_PORT" ]; then
            print_error "Proxy port cannot be empty"
            continue
        fi
        if ! [[ "$PROXY_PORT" =~ ^[0-9]+$ ]] || [ "$PROXY_PORT" -lt 1 ] || [ "$PROXY_PORT" -gt 65535 ]; then
            print_error "Port must be a number between 1 and 65535"
            continue
        fi
        
        # Test proxy with curl
        print_message "Testing proxy connection..."
        if [ "$PROXY_SCHEME" = "socks5" ]; then
            CURL_PROXY="socks5h://$PROXY_SERVER:$PROXY_PORT"
        else
            CURL_PROXY="$PROXY_SCHEME://$PROXY_SERVER:$PROXY_PORT"
        fi
        
        if curl --connect-timeout 10 -x "$CURL_PROXY" -s "https://api.telegram.org" >/dev/null 2>&1; then
            print_message "Successfully connected to proxy"
            
            read -p "👤 Enter proxy username (Enter = no authentication): " PROXY_USER
            if [ ! -z "$PROXY_USER" ]; then
                while true; do
                    read -s -p "🔑 Enter proxy password: " PROXY_PASS
                    echo
                    if [ -z "$PROXY_PASS" ]; then
                        print_error "Password cannot be empty"
                        continue
                    fi
                    break
                done
            fi
            break
        else
            print_error "Failed to connect to proxy"
            read -p "🔄 Would you like to try again? (Y/n): " RETRY
            if [[ $RETRY =~ ^[Nn]$ ]]; then
                USE_PROXY="n"
                break
            fi
        fi
    done
fi

# Create directory for bot
mkdir -p /var/www/html/bot

# Create config.json in project path
print_message "Creating config.json file..."
cat > config.json << EOL
{
    "api_id": "$API_ID",
    "api_hash": "$API_HASH",
    "bot_token": "$BOT_TOKEN",
    "allowed_chat_ids": $ALLOWED_JSON,
    "file_max_age_hours": $MAX_AGE,
    "your_domain": "$HOST",
    "download_path": "/var/www/html/dl"$([ ! -z "$USE_PROXY" ] && [ "$USE_PROXY" = "y" ] && echo ",
    \"proxy\": {
        \"scheme\": \"$PROXY_SCHEME\",
        \"server\": \"$PROXY_SERVER\",
        \"port\": $PROXY_PORT$([ ! -z "$PROXY_USER" ] && echo ",
        \"user\": \"$PROXY_USER\",
        \"pass\": \"$PROXY_PASS\"")
    }")
}
EOL

# Copy files to final location and set permissions
mkdir -p /var/www/html/bot
cp bot.py config.json /var/www/html/bot/
chown -R www-data:www-data /var/www/html/bot
chmod 600 /var/www/html/bot/config.json
chmod 600 config.json

print_message "Configuration file created successfully"
echo
print_warning "Entered information:"
echo "• API ID: $API_ID"
echo "• API Hash: ${API_HASH:0:6}..."
echo "• Bot Token: ${BOT_TOKEN:0:8}..."
echo "• Number of allowed users: ${#ALLOWED_ARRAY[@]}"
echo "• Maximum file age: $MAX_AGE hours"
if [[ $USE_PROXY =~ ^[Yy]$ ]]; then
    echo "• Proxy: $PROXY_SCHEME - $PROXY_SERVER:$PROXY_PORT"
fi
echo

# Create service file
print_message "Creating service file..."
cat > "$BOT_SERVICE" << EOL
[Unit]
Description=Telegram DL Bot Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$BOT_PATH
ExecStart=/usr/bin/python3 $BOT_PATH/DLBot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOL

# Set permissions and enable service
chmod 644 "$BOT_SERVICE"
print_message "Enabling service..."
systemctl daemon-reload
systemctl enable dlbot.service
systemctl start dlbot.service

print_message "Bot installed and started successfully!"
print_message "You can check the service status with:"
echo "   systemctl status dlbot.service"
echo
print_message "Services status:"
echo "nginx: $(systemctl is-active nginx)"
echo "telegrambot: $(systemctl is-active telegrambot)"
