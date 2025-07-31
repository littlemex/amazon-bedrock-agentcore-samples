手順

```bash
export AWS_PROFILE=xxx

# remote
uv run redeploy_agent.py

# local
uv run mcp_server.py

# local test
uv run my_mcp_client_remote3.py

# remote test
uv run my_mcp_client_remote3.py --mode=remote --use-uuid-fixer
```