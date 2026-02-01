"""Quick Redis Cloud connection test."""

import asyncio
import os
from redis.asyncio import Redis

async def test_connection():
    """Test Redis Cloud connection."""
    
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        print("❌ REDIS_URL environment variable not set!")
        print("Please set it in your .env file or export it:")
        print("export REDIS_URL='redis://default:PASSWORD@HOST:PORT'")
        return False
    
    # Hide password in output
    display_url = redis_url.split('@')[-1] if '@' in redis_url else redis_url
    
    print("Testing Redis Cloud connection...")
    print(f"Host: {display_url}")
    print()
    
    try:
        # Connect to Redis Cloud
        redis = Redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        
        # Test PING
        print("1. Testing PING...")
        response = await redis.ping()
        print(f"   ✓ PING successful: {response}")
        
        # Test SET
        print("\n2. Testing SET...")
        await redis.set('test_key', 'hello_from_piedpiper')
        print("   ✓ SET successful")
        
        # Test GET
        print("\n3. Testing GET...")
        value = await redis.get('test_key')
        print(f"   ✓ GET successful: {value}")
        
        # Test INFO
        print("\n4. Getting server info...")
        info = await redis.info('server')
        print(f"   ✓ Redis version: {info.get('redis_version')}")
        print(f"   ✓ Redis mode: {info.get('redis_mode')}")
        
        # Check for Redis Stack modules
        print("\n5. Checking Redis Stack modules...")
        modules = await redis.execute_command('MODULE', 'LIST')
        print(f"   ✓ Loaded modules: {len(modules)}")
        for module in modules:
            module_name = module[1].decode() if isinstance(module[1], bytes) else module[1]
            print(f"      - {module_name}")
        
        # Cleanup
        await redis.delete('test_key')
        await redis.close()
        
        print("\n" + "="*60)
        print("✅ Redis Cloud connection successful!")
        print("✅ Ready to use for PiedPiper")
        print("="*60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Connection failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_connection())
    exit(0 if success else 1)
