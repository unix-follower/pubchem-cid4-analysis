import asyncio
import json
import os

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
import env_utils


async def main():
    cwd = os.getcwd()
    print(f"Current working directory: {cwd}")

    server = StdioServerParameters(
        command="uv",
        args=["run", "python", "src/cid4_mcp.py"],
        cwd=cwd,
        env={
            "DATA_DIR": env_utils.get_data_dir(),
        },
    )

    async with (
        stdio_client(server) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        await session.initialize()

        tools = await session.list_tools()
        print("TOOLS:")
        for tool in tools.tools:
            print(f"- {tool.name}")

        result = await session.call_tool("get_compound_metadata", {})
        print("\nTOOL RESULT:")
        print("result:", result)
        print("isError:", result.isError)
        print("content:", [item.text for item in result.content if hasattr(item, "text")])
        print("structuredContent:")
        print(json.dumps(result.structuredContent, indent=2))

        resource = await session.read_resource("cid4://capabilities")
        print("\nRESOURCE:")
        for item in resource.contents:
            if hasattr(item, "text"):
                print(item.text)


if __name__ == "__main__":
    asyncio.run(main())
