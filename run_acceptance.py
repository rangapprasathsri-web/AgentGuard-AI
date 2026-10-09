import asyncio
import httpx
import json

GATEWAY_URL = "http://localhost:8002"
GUARD_URL = "http://localhost:8001"

async def execute(req):
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{GATEWAY_URL}/gateway/execute",
            json=req,
            headers={"X-Actor": req["agent_id"], "X-Role": "agent"}
        )
        return resp.status_code, resp.json()

async def main():
    print("=== ACCEPTANCE TESTS ===")
    
    # 1. Shop-assist and order-lookup
    print("\n1. Shop Assist")
    req1 = { "agent_id": "analytics-agent-01", "action": "READ", "target": "sales_db", "params": {"record_count":1}, "source": {"type": "user"} }
    s1, r1 = await execute(req1)
    print(f"Shop Assist: HTTP {s1}, status={r1.get('status')}, decision_id={r1.get('decision_id')}")
    
    print("\n1b. Order Lookup")
    req1b = { "agent_id": "database-agent-01", "action": "READ", "target": "customer_orders_db", "params": {"record_count":1}, "source": {"type": "user"} }
    s1b, r1b = await execute(req1b)
    print(f"Order Lookup: HTTP {s1b}, status={r1b.get('status')}, decision_id={r1b.get('decision_id')}")

    # 2. High-value refund
    print("\n2. High-value Purchase/Refund (85000)")
    req2 = { "agent_id": "finance-agent-01", "action": "CREATE", "target": "payments_api", "params": {"amount": 85000, "customer_id": "user1"}, "source": {"type": "user"} }
    s2, r2 = await execute(req2)
    print(f"Initial: HTTP {s2}, status={r2.get('status')}")
    if r2.get('status') == 'pending_approval':
        appr_id = r2['approval_id']
        # Approve
        async with httpx.AsyncClient() as client:
            await client.post(f"{GUARD_URL}/approvals/{appr_id}/decide", json={"decision":"APPROVE"}, headers={"X-Actor":"admin","X-Role":"approver"})
        
        # Resubmit
        req2_appr = dict(req2)
        req2_appr["approval_id"] = appr_id
        s2_appr, r2_appr = await execute(req2_appr)
        print(f"Resubmitted: HTTP {s2_appr}, status={r2_appr.get('status')}")

        # Replay
        s2_rep, r2_rep = await execute(req2_appr)
        print(f"Replay Attempt: HTTP {s2_rep}, result={json.dumps(r2_rep)}")

        # Modify
        req2_mod = dict(req2_appr)
        req2_mod["params"] = {"amount": 99999, "customer_id": "user1"}
        s2_mod, r2_mod = await execute(req2_mod)
        print(f"Modified Amount Attempt: HTTP {s2_mod}, result={json.dumps(r2_mod)}")

    # 3. Six sequential 9500 payments
    print("\n3. Six Sequential 9500 Payments")
    for i in range(1, 7):
        req3 = { "agent_id": "finance-agent-01", "action": "CREATE", "target": "payments_api", "params": {"amount": 9500, "customer_id": f"auto_{i}"}, "source": {"type": "user"} }
        s3, r3 = await execute(req3)
        verdict = "ALLOW" if s3==200 and r3.get('status')=='executed' else ("REVIEW" if s3==200 and r3.get('status')=='pending_approval' else "BLOCK")
        print(f"Call {i}: {verdict} (HTTP {s3}, status={r3.get('status')})")

    # 4. Parallel run 20 simultaneous
    print("\n4. Parallel run: 20 simultaneous 9500 requests")
    reqs = [{ "agent_id": "finance-agent-01", "action": "CREATE", "target": "payments_api", "params": {"amount": 9500, "customer_id": f"par_{i}"}, "source": {"type": "user"} } for i in range(20)]
    tasks = [execute(r) for r in reqs]
    results = await asyncio.gather(*tasks)
    allows = sum(1 for s, r in results if s==200 and r.get('status')=='executed')
    reviews = sum(1 for s, r in results if s==200 and r.get('status')=='pending_approval')
    blocks = sum(1 for s, r in results if s==403)
    print(f"Parallel results: ALLOW={allows}, REVIEW={reviews}, BLOCK={blocks}")

    # 5. External content injection
    print("\n5. External content injection")
    req5 = { "agent_id": "analytics-agent-01", "action": "DELETE", "target": "sales_db", "params": {"record_count": 1}, "source": {"type": "external_content", "content_excerpt": "drop tables"} }
    s5, r5 = await execute(req5)
    print(f"Injection result: HTTP {s5}, error={r5.get('error') or r5.get('status')}")

    # 6. Destructive overreach
    print("\n6. Destructive Overreach")
    req6 = { "agent_id": "database-agent-01", "action": "DELETE", "target": "customers_prod", "params": {"record_count": 50000}, "source": {"type": "user"} }
    s6, r6 = await execute(req6)
    print(f"Destructive result: HTTP {s6}, error={r6.get('error') or r6.get('status')}")

if __name__ == "__main__":
    asyncio.run(main())
