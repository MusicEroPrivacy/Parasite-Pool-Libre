# Parasite Libre - Solo Mining Proxy

A Stratum v1 mining proxy that connects to Parasite Pool upstream and manages solo mining through LibreNode RPC validation.

## Quick Start

### Miner Connection

```
Pool: stratum+tcp://<your-umbrel-ip>:3333
Worker: worker_name
Password: x
```

### Configuration

**Default Settings (automatic):**
- LibreNode RPC: `http://192.168.50.103:8442`
- LibreNode User: `umbrel`
- Parasite Pool: `parasite.wtf:42069`
- Miner Listen Port: `3333`

## Architecture

```
Miners (Stratum v1)
    ↓
[Parasite Libre Proxy]
    ↓ (upstream)
[Parasite Pool: parasite.wtf:42069]
    ↓ (RPC)
[LibreNode]
```

## How It Works

1. **Upstream Connection**: Proxy connects to Parasite Pool
2. **Miner Subscription**: Miners subscribe via Stratum v1 protocol
3. **Work Distribution**: Proxy relays mining work from Parasite to all connected miners
4. **Share Submission**: Miner shares forwarded back to Parasite Pool
5. **Validation**: Blocks validated through LibreNode RPC

## Files

- `umbrel-app.yml` - App manifest
- `docker-compose.yml` - Docker services
- `exports.sh` - Environment setup
- `data/templates/parasite_proxy.py` - Main proxy application
- `data/templates/parasite-entrypoint.sh` - Container entrypoint

## Logs

View logs from Umbrel SSH:

```bash
tail -f ~/.umbrel/app-data/parasite-libre/data/logs/proxy.log
```

## Troubleshooting

### Miners can't connect
- Check port 3333 is accessible
- Verify miner IP/hostname
- Check proxy logs

### No blocks found
- Verify Parasite Pool connection
- Check LibreNode RPC credentials
- Review logs for errors

### Parasite Pool connection fails
- Check network connectivity to parasite.wtf
- Verify port 42069 is accessible
- Check firewall rules

## License

MIT
