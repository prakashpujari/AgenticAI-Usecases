"""
src/generation/__init__.py
──────────────────────────
Generation sub-package.

Responsible for:
  • Building the LangChain LCEL chain (prompt → LLM → output parser)
  • Retrieving broad context chunks from the FAISS vector store
  • Invoking the OpenAI Chat API to generate original Q&A
  • Parsing and validating the JSON response
"""
