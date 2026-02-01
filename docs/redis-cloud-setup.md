# Redis Cloud Setup Guide

This guide walks you through setting up Redis Cloud for the PiedPiper application.

## Why Redis Cloud?

- ✅ **No Docker needed** - Cloud-hosted, always available
- ✅ **Free tier** - 30MB storage (enough for ~2000 cached Q&A pairs)
- ✅ **Redis Stack included** - Vector search, JSON, full-text search
- ✅ **Automatic backups** - Your data is safe
- ✅ **Global availability** - Access from anywhere
- ✅ **SSL/TLS support** - Secure connections

## Step-by-Step Setup

### 1. Create Redis Cloud Account

1. Go to https://redis.com/try-free/
2. Click "Get started free"
3. Sign up with email or Google/GitHub
4. Verify your email

### 2. Create a Database

1. After login, click **"New database"** or **"Create database"**

2. **Choose subscription type:**
   - Select **"Fixed"** (free tier)
   - Or **"Flexible"** if you need more than 30MB

3. **Database settings:**
   - **Name:** `piedpiper-cache`
   - **Type:** Select **"Redis Stack"** ⚠️ IMPORTANT (needed for vector search)
   - **Region:** Choose closest to your location (e.g., `us-east-1`)
   - **Memory:** 30MB (free tier)

4. Click **"Create Database"**

### 3. Get Connection Details

Once the database is created:

1. Click on your database name
2. Go to **"Configuration"** tab
3. Note these details:
   - **Public endpoint:** `redis-xxxxx.c123.us-east-1.cloud.redislabs.com:12345`
   - **Username:** `default` (usually)
   - **Password:** Click "eye" icon to reveal

### 4. Configure Your Application

Create or update your `.env` file:

```bash
# Copy from .env.example
cp .env.example .env

# Edit .env and update:
REDIS_URL=redis://default:YOUR_PASSWORD@redis-xxxxx.c123.us-east-1.cloud.redislabs.com:12345

# For SSL (recommended for production):
REDIS_URL=rediss://default:YOUR_PASSWORD@redis-xxxxx.c123.us-east-1.cloud.redislabs.com:12345
```

**Example:**
```bash
REDIS_URL=redis://default:AbCdEf123456@redis-15166.c258.us-east-1-4.ec2.cloud.redislabs.com:15166
```

### 5. Test Connection

```bash
# Set environment variables
export OPENAI_API_KEY="sk-..."
export REDIS_URL="redis://default:YOUR_PASSWORD@redis-xxxxx.c123.region.cloud.redislabs.com:12345"

# Run test
python backend/tests/test_redis_integration.py
```

Expected output:
```
============================================================
Testing Redis Integration (Redis Cloud)
============================================================
Redis URL: redis-xxxxx.c123.region.cloud.redislabs.com:12345

1. Connecting to Redis Cloud...
✓ Redis Cloud connected
...
✓ All tests passed!
```

## Verification Checklist

- [ ] Redis Cloud account created
- [ ] Database created with **Redis Stack** type
- [ ] Connection details copied (host, port, password)
- [ ] `.env` file updated with `REDIS_URL`
- [ ] Test script runs successfully
- [ ] Can see data in Redis Insight (optional)

## Using Redis Insight (Optional)

Redis Cloud includes a web-based Redis Insight UI:

1. Go to your database in Redis Cloud
2. Click **"Tools"** tab
3. Click **"Redis Insight"**
4. Browse your data, run queries, monitor performance

Or download desktop version: https://redis.com/redis-enterprise/redis-insight/

## Troubleshooting

### Connection Refused

**Symptom:** `ConnectionError: Error connecting to Redis`

**Solutions:**
- Check if password is correct in `REDIS_URL`
- Verify the host and port are correct
- Check if database is active in Redis Cloud dashboard
- Try with SSL: change `redis://` to `rediss://`

### SSL Certificate Error

**Symptom:** `SSL: CERTIFICATE_VERIFY_FAILED`

**Solution:**
```bash
# Use rediss:// with SSL
REDIS_URL=rediss://default:password@host:port

# Or disable SSL verification (development only)
REDIS_URL=redis://default:password@host:port
```

### Module Not Found Error

**Symptom:** `Redis module 'search' not found`

**Solution:**
- Recreate database and select **"Redis Stack"** type
- Free tier must use Redis Stack, not plain Redis

### Memory Limit Exceeded

**Symptom:** `OOM command not allowed when used memory > 'maxmemory'`

**Solutions:**
- Upgrade to larger plan
- Delete old cached data
- Reduce embedding dimensions
- Implement TTL-based eviction

## Free Tier Limits

| Feature | Limit |
|---------|-------|
| Storage | 30 MB |
| Cached Q&A pairs | ~2,000 |
| Connections | 30 concurrent |
| Bandwidth | Unlimited |
| Throughput | ~2,500 ops/sec |
| Backup | 1 per day |

**Storage calculation:**
- Each Q&A pair: ~15KB (with embeddings)
- 30MB ÷ 15KB ≈ 2,000 pairs

## Upgrading from Free Tier

When you need more storage:

1. Go to database settings
2. Click **"Edit database"**
3. Increase memory size
4. Choose billing plan

**Pricing (as of 2024):**
- Free: 30MB
- $5/month: 250MB
- $10/month: 1GB
- Enterprise: Custom

## Security Best Practices

### Development
```bash
# .env (not committed to git)
REDIS_URL=redis://default:password@host:port
```

### Production
```bash
# Use SSL
REDIS_URL=rediss://default:password@host:port

# Or use ACL for fine-grained access
REDIS_URL=rediss://custom_user:password@host:port
```

### Environment Variables
- ✅ Store credentials in `.env` (gitignored)
- ✅ Use different databases for dev/staging/prod
- ✅ Rotate passwords regularly
- ❌ Never commit `.env` to git
- ❌ Never hardcode passwords in code

## Monitoring

Redis Cloud provides:
- **Dashboard:** Real-time metrics (ops/sec, memory usage, connections)
- **Alerts:** Email notifications for errors
- **Logs:** Access and error logs
- **Latency:** P50, P95, P99 metrics

Access via: Database → Metrics tab

## Next Steps

Once Redis Cloud is configured:

1. ✅ Run the integration test
2. ✅ Start the FastAPI backend: `uvicorn piedpiper.main:app --reload`
3. ✅ Verify indices are created on startup
4. ✅ Test the workflow with actual agent queries

## Support

- **Redis Cloud Docs:** https://docs.redis.com/latest/rc/
- **Redis Stack Docs:** https://redis.io/docs/stack/
- **Support:** support@redis.com (paid tiers)
- **Community:** Redis Discord - https://discord.gg/redis
