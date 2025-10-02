#!/bin/bash

# Colors used for messages
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
BOLD='\033[1m'
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

print_info() {
    echo -e "${CYAN}[i]${NC} $1"
}

print_step() {
    echo -e "\n${MAGENTA}┌─────────────────────────────────────┐${NC}"
    echo -e "${MAGENTA}│${NC} ${BOLD}$1${NC}"
    echo -e "${MAGENTA}└─────────────────────────────────────┘${NC}\n"
}

print_input_prompt() {
    echo -en "${BLUE}$1${NC}"
}

# Important paths and names
BOT_PATH="/opt/Telegram-File-to-Link"
SERVICE_NAME="$(basename "$BOT_PATH")"
BOT_SERVICE="/etc/systemd/system/$SERVICE_NAME.service"

# Check for uninstall parameter immediately
if [ "$1" = "--uninstall" ]; then
    print_step "🗑️ Uninstalling Telegram File to Link Bot"
    
    # Stop and disable service
    print_message "Stopping and disabling bot service..."
    systemctl stop "$SERVICE_NAME.service"
    systemctl disable "$SERVICE_NAME.service"
    rm -f "/etc/systemd/system/$SERVICE_NAME.service"
    systemctl daemon-reload
    
    # Remove nginx configuration
    print_message "Removing nginx configuration..."
    rm -f "/etc/nginx/sites-enabled/$SERVICE_NAME"
    rm -f "/etc/nginx/sites-available/$SERVICE_NAME"
    systemctl restart nginx
    
    # Remove bot files
    print_message "Removing bot files..."
    rm -rf "$BOT_PATH"
    rm -rf "/var/www/html/dl"
    
    print_message "✨ Bot uninstalled successfully!"
    echo
    print_warning "Note: SSL certificates were preserved at /root/cert/"
    print_warning "You can manually remove them if needed."
    exit 0
fi

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
git clone https://github.com/ArashAfkandeh/Telegram-File-to-Link.git || {
    print_error "Failed to clone repository"
    exit 1
}

# Move to /opt
print_message "Moving to $BOT_PATH..."
if [ -d "$BOT_PATH" ]; then
    rm -rf "$BOT_PATH"
fi
mv Telegram-File-to-Link "$BOT_PATH"
print_message "Repository installed to $BOT_PATH successfully"

# Set proper permissions for the bot directory
print_message "Setting proper permissions..."
chown -R root:root "$BOT_PATH"
chmod -R 755 "$BOT_PATH"

# Install or update required Python packages
print_message "Installing Python libraries..."
python3 -m pip install --upgrade pip
python3 -m pip install pyrogram tgcrypto psutil uvloop

# Create required directories
print_message "Creating required directories..."
mkdir -p /var/www/html/dl
chown -R root:root /var/www/html
chmod -R 755 /var/www/html

# Get command line arguments
print_step "💫 Welcome to Telegram File Hosting Bot Setup 💫"
print_info "Please provide the following information to configure your bot:"
echo

if [ -z "$1" ]; then
    print_input_prompt "🌐 Enter your domain name: "
    read HOST < /dev/tty
    while [ -z "$HOST" ]; do
        print_error "Domain name cannot be empty"
        print_input_prompt "🌐 Please enter your domain name: "
        read HOST < /dev/tty
    done
else
    HOST="$1"
    print_message "Domain name: $HOST"
fi

if [ -z "$2" ]; then
    print_input_prompt "📧 Enter your email address: "
    read EMAIL < /dev/tty
    while [ -z "$EMAIL" ]; do
        print_error "Email cannot be empty"
        print_input_prompt "📧 Please enter your email address: "
        read EMAIL < /dev/tty
    done
else
    EMAIL="$2"
    print_message "Email address: $EMAIL"
fi

if [ -z "$3" ]; then
    echo -e "\n${CYAN}ℹ️  To get API credentials:${NC}"
    echo -e "   1. Go to ${BLUE}https://my.telegram.org/apps${NC}"
    echo -e "   2. Create a new application"
    echo -e "   3. Copy the ${YELLOW}api_id${NC} and ${YELLOW}api_hash${NC}\n"
    
    print_input_prompt "🔑 Enter your Telegram api_id: "
    read API_ID < /dev/tty
else
    API_ID="$3"
    print_message "API ID configured"
fi

if [ -z "$4" ]; then
    print_input_prompt "🔑 Enter your Telegram api_hash: "
    read API_HASH < /dev/tty
else
    API_HASH="$4"
    print_message "API Hash configured"
fi

if [ -z "$5" ]; then
    echo -e "\n${CYAN}ℹ️  To get a bot token:${NC}"
    echo -e "   1. Start a chat with ${BLUE}@BotFather${NC} on Telegram"
    echo -e "   2. Send /newbot and follow the instructions"
    echo -e "   3. Copy the provided token\n"
    
    print_input_prompt "🤖 Enter your bot token: "
    read BOT_TOKEN < /dev/tty
else
    BOT_TOKEN="$5"
    print_message "Bot token configured"
fi

# SSL variables
CERT_DIR="/root/cert/$HOST"
KEY_FILE="$CERT_DIR/privkey.pem"
CHAIN_FILE="$CERT_DIR/fullchain.pem"

# Set up temporary nginx config for ACME challenge
print_message "Configuring nginx for domain ownership verification..."
cat > "/etc/nginx/sites-available/$SERVICE_NAME" << EOL
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

# Clean up any erroneous directories or files in sites-enabled
rm -f /etc/nginx/sites-enabled/default
if [ -d "/etc/nginx/sites-enabled/sites-available" ]; then
    rm -rf "/etc/nginx/sites-enabled/sites-available"
    print_warning "Removed erroneous 'sites-available' directory in sites-enabled"
fi
rm -f "/etc/nginx/sites-enabled/$SERVICE_NAME"

# Enable temporary configuration
ln -sf "/etc/nginx/sites-available/$SERVICE_NAME" "/etc/nginx/sites-enabled/$SERVICE_NAME"

# Test and restart nginx
nginx -t && systemctl restart nginx || {
    print_error "Nginx configuration test failed during temporary setup!"
    exit 1
}

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

# acme.sh automatically handles the cron job for renewal.
# The manual entry is removed to prevent errors.

# Configure nginx with optimized settings
print_message "Configuring nginx with SSL..."
cat > "/etc/nginx/sites-available/$SERVICE_NAME" << EOL
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
    ssl_protocols TLSv1.3;
    ssl_prefer_server_ciphers off;
    ssl_ciphers EECDH+CHACHA20:EECDH+AESGCM:EECDH+AES;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:10m;
    ssl_session_tickets off;
    ssl_stapling on;
    ssl_stapling_verify on;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-XSS-Protection "1; mode=block" always;

    root /var/www/html;
    index index.html;

    gzip on;
    gzip_types text/plain application/xml text/css application/javascript;
    gzip_min_length 1000;

    location /dl/ {
        alias /var/www/html/dl/;
        autoindex off;
        try_files \$uri \$uri/ =404;
        expires 30d;
        add_header Cache-Control "public";
    }

    location / {
        try_files \$uri \$uri/ =404;
    }
}
EOL

# Clean up before enabling
rm -f /etc/nginx/sites-enabled/default
if [ -d "/etc/nginx/sites-enabled/sites-available" ]; then
    rm -rf "/etc/nginx/sites-enabled/sites-available"
    print_warning "Removed erroneous 'sites-available' directory in sites-enabled"
fi
rm -f "/etc/nginx/sites-enabled/$SERVICE_NAME"

# Enable nginx configuration
ln -sf "/etc/nginx/sites-available/$SERVICE_NAME" "/etc/nginx/sites-enabled/$SERVICE_NAME"

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
print_step "🔧 Creating System Service"
print_message "Setting up systemd service for the bot..."

cat > "$BOT_SERVICE" << EOL
[Unit]
Description=Telegram File to Link Bot
After=network.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=$BOT_PATH
ExecStart=/usr/bin/python3 $BOT_PATH/bot.py
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

# Validate api_id
if ! validate_api_id "$API_ID"; then
    print_error "api_id must be an integer"
    exit 1
fi

# Validate api_hash
if ! validate_api_hash "$API_HASH"; then
    print_error "api_hash must be a 32-character hexadecimal string"
    exit 1
fi

# Validate bot_token
if ! validate_bot_token "$BOT_TOKEN"; then
    print_error "Invalid bot token format"
    exit 1
fi

print_step "👥 User Access Configuration 👥"
echo -e "${CYAN}ℹ️  User Access Control:${NC}"
echo -e "   ${YELLOW}•${NC} You can restrict bot access to specific users"
echo -e "   ${YELLOW}•${NC} Enter Telegram user IDs separated by commas"
echo -e "   ${YELLOW}•${NC} Leave empty to allow access for all users"
echo -e "   ${YELLOW}•${NC} Example: 123456789,987654321\n"

print_input_prompt "Enter allowed user IDs (press Enter for public access): "
read ALLOWED_USERS < /dev/tty

if [ -z "$ALLOWED_USERS" ]; then
    ALLOWED_JSON="[]"
    print_message "✨ Bot will be accessible to all users"
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
    print_message "🔒 Access restricted to ${#ALLOWED_ARRAY[@]} specified users"
fi

print_step "⚙️ File Management Settings ⚙️"
echo -e "${CYAN}ℹ️  About File Age Limit:${NC}"
echo -e "   ${YELLOW}•${NC} Files older than this limit will be automatically deleted"
echo -e "   ${YELLOW}•${NC} This helps manage server storage space"
echo -e "   ${YELLOW}•${NC} Recommended: 24-72 hours depending on your needs"
echo -e "   ${YELLOW}•${NC} Users should download their files within this time\n"

print_input_prompt "Enter maximum file age in hours [Enter = 24]: "
read MAX_AGE < /dev/tty
if [ -z "$MAX_AGE" ]; then
    MAX_AGE=24
    print_message "⏳ Using default value of 24 hours"
else
    if [[ "$MAX_AGE" =~ ^[0-9]+$ ]]; then
        print_message "⏳ Files will be kept for $MAX_AGE hours"
    else
        print_error "Invalid input. Using default value of 24 hours"
        MAX_AGE=24
    fi
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
print_step "🌐 Checking Connection to Telegram 🌐"

if check_telegram_connection; then
    print_message "✨ Connection to Telegram is working perfectly! No proxy needed."
    USE_PROXY="n"
else
    print_warning "⚠️ Unable to establish connection to Telegram servers"
    echo
    echo -e "${CYAN}ℹ️  Proxy Configuration Options:${NC}"
    echo -e "   ${YELLOW}•${NC} Using a proxy can help if Telegram is blocked"
    echo -e "   ${YELLOW}•${NC} Supports SOCKS5, HTTP, and HTTPS proxies"
    echo -e "   ${YELLOW}•${NC} You can skip this if you're unsure\n"
    
    while true; do
        print_input_prompt "Would you like to configure a proxy? [y/N]: "
        read USE_PROXY_INPUT < /dev/tty
        case $USE_PROXY_INPUT in
            [Yy]* )
                USE_PROXY="y"
                break
                ;;
            [Nn]* | "" )
                print_warning "Continuing without proxy configuration"
                USE_PROXY="n"
                break
                ;;
            * )
                print_error "Please enter 'y' for yes or 'n' for no"
                ;;
        esac
    done
fi
if [[ $USE_PROXY =~ ^[Yy]$ ]]; then
    # Proxy settings as required values
    MAX_PROXY_ATTEMPTS=3
    PROXY_ATTEMPT=1
    
    while [ $PROXY_ATTEMPT -le $MAX_PROXY_ATTEMPTS ]; do
        print_message "Proxy configuration attempt $PROXY_ATTEMPT of $MAX_PROXY_ATTEMPTS"
        
        # Get proxy type
        read -p "🔧 Enter proxy type (Enter = socks5): " PROXY_SCHEME < /dev/tty
        if [ -z "$PROXY_SCHEME" ]; then
            PROXY_SCHEME="socks5"
            print_message "Proxy type set to socks5"
        fi
        
        # Get proxy address with validation
        for i in {1..3}; do
            read -p "🖥️ Enter proxy server address: " PROXY_SERVER < /dev/tty
            if [ -z "$PROXY_SERVER" ]; then
                print_error "Proxy address cannot be empty (attempt $i of 3)"
                [ $i -eq 3 ] && {
                    print_error "Maximum attempts reached for proxy address"
                    exit 1
                }
                continue
            fi
            break
        done
        
        # Get proxy port with validation
        for i in {1..3}; do
            read -p "🔌 Enter proxy port: " PROXY_PORT < /dev/tty
            if [ -z "$PROXY_PORT" ]; then
                print_error "Proxy port cannot be empty (attempt $i of 3)"
                [ $i -eq 3 ] && {
                    print_error "Maximum attempts reached for proxy port"
                    exit 1
                }
                continue
            fi
            if ! [[ "$PROXY_PORT" =~ ^[0-9]+$ ]] || [ "$PROXY_PORT" -lt 1 ] || [ "$PROXY_PORT" -gt 65535 ]; then
                print_error "Port must be a number between 1 and 65535 (attempt $i of 3)"
                [ $i -eq 3 ] && {
                    print_error "Maximum attempts reached for proxy port"
                    exit 1
                }
                continue
            fi
            break
        done
        
        # Test proxy with curl
        print_message "Testing proxy connection..."
        if [ "$PROXY_SCHEME" = "socks5" ]; then
            CURL_PROXY="socks5h://$PROXY_SERVER:$PROXY_PORT"
        else
            CURL_PROXY="$PROXY_SCHEME://$PROXY_SERVER:$PROXY_PORT"
        fi
        
        if curl --connect-timeout 10 -x "$CURL_PROXY" -s "https://api.telegram.org" >/dev/null 2>&1; then
            print_message "Successfully connected to proxy"
            
            # Get proxy authentication if needed
            read -p "👤 Enter proxy username (Enter = no authentication): " PROXY_USER < /dev/tty
            if [ ! -z "$PROXY_USER" ]; then
                for i in {1..3}; do
                    read -s -p "🔑 Enter proxy password: " PROXY_PASS < /dev/tty
                    echo
                    if [ -z "$PROXY_PASS" ]; then
                        print_error "Password cannot be empty (attempt $i of 3)"
                        [ $i -eq 3 ] && {
                            print_error "Maximum attempts reached for proxy password"
                            exit 1
                        }
                        continue
                    fi
                    break
                done
            fi
            break
        else
            print_error "Failed to connect to proxy"
            if [ $PROXY_ATTEMPT -lt $MAX_PROXY_ATTEMPTS ]; then
                read -p "🔄 Would you like to try again? (Y/n): " RETRY < /dev/tty
                if [[ $RETRY =~ ^[Nn]$ ]]; then
                    print_warning "Continuing without proxy"
                    USE_PROXY="n"
                    break
                fi
            else
                print_error "Maximum proxy configuration attempts reached"
                print_warning "Continuing without proxy"
                USE_PROXY="n"
                break
            fi
        fi
        
        PROXY_ATTEMPT=$((PROXY_ATTEMPT + 1))
    done
fi

# Create config.json in project path
if [[ $USE_PROXY != "y" ]]; then
    PROXY_SCHEME="socks5"
    PROXY_SERVER=""
    PROXY_PORT=0
    PROXY_USER=""
    PROXY_PASS=""
fi

print_message "Creating config.json file..."
cat > "$BOT_PATH/config.json" << EOL
{
    "api_id": "$API_ID",
    "api_hash": "$API_HASH",
    "bot_token": "$BOT_TOKEN",
    "allowed_chat_ids": $ALLOWED_JSON,
    "file_max_age_hours": $MAX_AGE,
    "your_domain": "$HOST",
    "download_path": "/dl",
    "proxy": {
        "scheme": "$PROXY_SCHEME",
        "server": "$PROXY_SERVER",
        "port": $PROXY_PORT$([ ! -z "$PROXY_USER" ] && echo ",
        \"user\": \"$PROXY_USER\",
        \"pass\": \"$PROXY_PASS\"")
    }
}
EOL

# Set proper permissions
chmod 600 "$BOT_PATH/config.json"
chown -R root:root "$BOT_PATH"

print_step "🎉 Configuration Complete! 🎉"
print_message "Configuration file created successfully"
echo
echo -e "${CYAN}📋 Configuration Summary:${NC}"
echo -e "${MAGENTA}┌─────────────────────────────────────┐${NC}"
echo -e "${MAGENTA}│${NC} ${BOLD}API ID:${NC}        ${GREEN}$API_ID${NC}"
echo -e "${MAGENTA}│${NC} ${BOLD}API Hash:${NC}      ${GREEN}${API_HASH:0:6}...${NC}"
echo -e "${MAGENTA}│${NC} ${BOLD}Bot Token:${NC}     ${GREEN}${BOT_TOKEN:0:8}...${NC}"
echo -e "${MAGENTA}│${NC} ${BOLD}Allowed Users:${NC}  ${GREEN}${#ALLOWED_ARRAY[@]}${NC}"
echo -e "${MAGENTA}│${NC} ${BOLD}File Age:${NC}      ${GREEN}$MAX_AGE hours${NC}"
if [[ $USE_PROXY =~ ^[Yy]$ ]]; then
    echo -e "${MAGENTA}│${NC} ${BOLD}Proxy:${NC}         ${GREEN}$PROXY_SCHEME - $PROXY_SERVER:$PROXY_PORT${NC}"
fi
echo -e "${MAGENTA}└─────────────────────────────────────┘${NC}"
echo



# Set permissions and enable service
chmod 644 "$BOT_SERVICE"
print_step "🚀 Starting Bot Service"
print_message "Setting up system service '$SERVICE_NAME'..."
systemctl daemon-reload
systemctl enable "$SERVICE_NAME.service"
systemctl start "$SERVICE_NAME.service"

print_step "🎉 Installation Complete! 🎉"
print_message "Bot has been installed and started successfully!"

echo -e "\n${CYAN}ℹ️  Quick Commands:${NC}"
echo -e "${MAGENTA}┌─────────────────────────────────────┐${NC}"
echo -e "${MAGENTA}│${NC} Check service status:${NC}"
echo -e "${MAGENTA}│${NC} ${BLUE}systemctl status $SERVICE_NAME${NC}"
echo -e "${MAGENTA}│${NC}"
echo -e "${MAGENTA}│${NC} Restart the bot:${NC}"
echo -e "${MAGENTA}│${NC} ${BLUE}systemctl restart $SERVICE_NAME${NC}"
echo -e "${MAGENTA}└─────────────────────────────────────┘${NC}"

echo -e "\n${CYAN}📊 Current Services Status:${NC}"
echo -e "${MAGENTA}┌─────────────────────────────────────┐${NC}"
echo -e "${MAGENTA}│${NC} nginx:       $(systemctl is-active nginx | sed 's/active/\\${GREEN}active\\${NC}/' | sed 's/inactive/\\${RED}inactive\\${NC}/')"
echo -e "${MAGENTA}│${NC} $SERVICE_NAME: $(systemctl is-active $SERVICE_NAME | sed 's/active/\\${GREEN}active\\${NC}/' | sed 's/inactive/\\${RED}inactive\\${NC}/')"
echo -e "${MAGENTA}└─────────────────────────────────────┘${NC}"
