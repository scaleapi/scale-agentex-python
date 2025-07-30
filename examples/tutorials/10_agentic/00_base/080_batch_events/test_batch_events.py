#!/usr/bin/env python3
"""
Simple script to test agent RPC endpoints using the actual schemas.
"""

import httpx
import json
import uuid
import asyncio

# Configuration
BASE_URL = "http://localhost:5003"
# AGENT_ID = "b4f32d71-ff69-4ac9-84d1-eb2937fea0c7"
AGENT_ID = "58e78cd0-c898-4009-b5d9-eada8ebcad83"
RPC_ENDPOINT = f"{BASE_URL}/agents/{AGENT_ID}/rpc"

async def send_rpc_request(method: str, params: dict):
    """Send an RPC request to the agent."""
    request_data = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": method,
        "params": params
    }
    
    print(f"→ Sending: {method}")
    print(f"  Request: {json.dumps(request_data, indent=2)}")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                RPC_ENDPOINT,
                json=request_data,
                headers={"Content-Type": "application/json"},
                timeout=30.0
            )
            
            print(f"  Status: {response.status_code}")
            
            if response.status_code == 200:
                response_data = response.json()
                print(f"  Response: {json.dumps(response_data, indent=2)}")
                return response_data
            else:
                print(f"  Error: {response.text}")
                return None
                
        except Exception as e:
            print(f"  Failed: {e}")
            return None

async def main():
    """Main function to test the agent RPC endpoints."""
    print(f"🚀 Testing Agent RPC: {AGENT_ID}")
    print(f"🔗 Endpoint: {RPC_ENDPOINT}")
    print("=" * 50)
    
    # Step 1: Create a task
    print("\n📝 Step 1: Creating a task...")
    task_response = await send_rpc_request("task/create", {
        "params": {
            "description": "Test task from simple script"
        }
    })
    
    if not task_response or task_response.get("error"):
        print("❌ Task creation failed, continuing anyway...")
        task_id = str(uuid.uuid4())  # Generate a task ID to continue
    else:
        # Extract task_id from response (adjust based on actual response structure)
        task_id = task_response.get("result", {}).get("id", str(uuid.uuid4()))
    
    print(f"📋 Using task_id: {task_id}")
    
    # Step 2: Send messages
    print("\n📤 Step 2: Sending messages...")
    
    messages = [f"This is message {i}" for i in range(20)]
    
    for i, message in enumerate(messages, 1):
        print(f"\n📨 Sending message {i}/{len(messages)}")
        
        # Create message content using TextContent structure
        message_content = {
            "type": "text",
            "author": "user",
            "style": "static",
            "format": "plain",
            "content": message
        }
        
        # Send message using message/send method
        response = await send_rpc_request("event/send", {
            "task_id": task_id,
            "event": message_content,
        })
        
        if response and not response.get("error"):
            print(f"✅ Message {i} sent successfully")
        else:
            print(f"❌ Message {i} failed")
        
        # Small delay between messages
        await asyncio.sleep(0.1)
    
    print("\n" + "=" * 50)
    print("✨ Script completed!")
    print(f"📋 Task ID: {task_id}")

if __name__ == "__main__":
    asyncio.run(main()) 
