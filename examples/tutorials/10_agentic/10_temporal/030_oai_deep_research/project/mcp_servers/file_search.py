import asyncio
import json
import glob
from mcp.server import Server

server = Server("file-search")

@server.tool()
async def search_files(query: str, path: str = ".") -> str:
    """Search for files containing specific text"""
    matches = []
    for file in glob.glob(f"{path}/**/*.py", recursive=True):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                content = f.read()
                if query.lower() in content.lower():
                    matches.append({
                        "file": file,
                        "preview": content[:200]
                    })
        except Exception:
            pass
    
    # Also search for markdown and text files
    for extension in ["md", "txt"]:
        for file in glob.glob(f"{path}/**/*.{extension}", recursive=True):
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if query.lower() in content.lower():
                        matches.append({
                            "file": file,
                            "preview": content[:200]
                        })
            except Exception:
                pass
    
    return json.dumps(matches[:10])

if __name__ == "__main__":
    asyncio.run(server.run())