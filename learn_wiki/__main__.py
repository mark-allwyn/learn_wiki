import uvicorn
from learn_wiki.web.app import create_app
from learn_wiki.graph.store import GraphStore
from learn_wiki.extract.claude import ClaudeExtractor

store = GraphStore("learn_wiki.db")
store.init_schema()
app = create_app(store, ClaudeExtractor())

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
