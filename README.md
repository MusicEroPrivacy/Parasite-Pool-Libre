# Parasite Pool + LibreNode Umbrel App

A Stratum v1 proxy that connects to Parasite Pool upstream and manages solo mining shares through your local LibreNode instance on Umbrel.

## Features

- **Parasite Pool Integration**: Direct connection to parasite.wtf:42069
- **LibreNode Backend**: Uses local LibreNode RPC for block validation and submission
- **Stratum v1 Protocol**: Compatible with standard mining software
- **Multi-Miner Support**: Handle multiple miners connecting simultaneously
- **Auto-Reconnect**: Automatic reconnection on upstream failure
- **Detailed Logging**: Comprehensive logging for debugging

## Architecture

```
Miners (Stratum v1) 
    ↓
[Parasite Proxy]
    ↓ (upstream)
[Parasite Pool]
    ↓ (RPC)
[LibreNode]
```

## Configuration

### Default Settings (set in `exports.sh`)

- **LibreNode RPC**: `http://192.168.50.103:8442`
- **LibreNode User**: `umbrel`
- **Parasite Pool**: `parasite.wtf:42069`
- **Miner Listen Port**: `3333`

### Miner Configuration

Connect your miner using:

```
stratum+tcp://<your-umbrel-ip>:3333
Worker: <any-name>
Password: <anything>
```

Example with cgminer:

```bash
cgminer -o stratum+tcp://192.168.50.103:3333 -u worker1 -p x
```

## How It Works

1. **Connection**: Proxy connects to Parasite Pool upstream
2. **Subscription**: Miners subscribe to the proxy using Stratum v1 protocol
3. **Authorization**: Miners authorize with a worker name
4. **Work Distribution**: Proxy receives mining work from Parasite and sends to all connected miners
5. **Share Submission**: Miner shares are sent back to Parasite Pool
6. **Block Validation**: Valid blocks are validated through LibreNode RPC

## Files

- `umbrel-app.yml` - Umbrel app manifest
- `docker-compose.yml` - Docker services configuration
- `exports.sh` - Environment variable setup (includes credentials)
- `data/templates/parasite_proxy.py` - Main proxy application
- `data/templates/parasite-proxy-entrypoint.sh` - Container entrypoint
- `data/templates/proxy-config.template` - Configuration template

## Logs

Logs are stored in `/data/logs/proxy.log` within the app data directory.

View logs:
```bash
tail -f <umbrel-data-dir>/parasite-pool-libre/data/logs/proxy.log
```

## Installation

1. Clone or download this repository
2. Add to your Umbrel community store
3. Install from the Umbrel app store
4. Configure LibreNode credentials (if needed)
5. Connect your miners to the proxy

## Troubleshooting

### No upstream connection
- Check network connectivity to parasite.wtf
- Verify port 42069 is accessible
- Check firewall rules

### Miners can't connect
- Verify port 3333 is exposed/accessible
- Check miner configuration
- Review proxy logs

### Blocks not submitting
- Verify LibreNode RPC credentials
- Check LibreNode is synced and running
- Review RPC error logs

## License

MIT
