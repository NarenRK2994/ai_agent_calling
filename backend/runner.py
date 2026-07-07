"""Concrete backend workflow runner that only requires a question input."""

from __future__ import annotations

from uuid import uuid4

from agents.execution_agent import ExecutionAgent
from agents.intent_agent import IntentAgent
from agents.prompt_builder_agent import PromptBuilderAgent
from agents.schema_agent import SchemaAgent
from agents.sql_agent import SQLAgent
from agents.summary_agent import SummaryAgent
from agents.validation_agent import ValidationAgent
from backend.application import ApplicationContext
from database.oracle import OracleDatabaseClient
from graph.state import ERPAgentState
from graph.workflow import build_workflow, execute_workflow
from llm.qwen import QwenLLM
from retriever.embedding import EmbeddingService
from retriever.retriever import LangChainSchemaRetriever
from retriever.schema_loader import SchemaLoader
from retriever.vector_store import ChromaVectorStore
from utils.prompt_loader import PromptTemplateLoader


def run_question(
    *,
    question: str,
    runtime,
    context: ApplicationContext,
):
    """Run the ERP AI Agent end to end using only a user question as input."""
    prompt_loader = PromptTemplateLoader(context.config.prompt_dir)
    llm = QwenLLM(
        model_name=context.config.llm.model_name,
        temperature=context.config.llm.temperature,
        context_window=context.config.llm.context_window,
        max_new_tokens=context.config.llm.max_new_tokens,
        device_map=context.config.llm.device,
        prompt_loader=prompt_loader,
    )

    schema_loader = SchemaLoader()
    schema_loader.load(context.config.metadata_dir)

    embedding_service = EmbeddingService(
        model_name=context.config.embedding.model_name,
        device=context.config.embedding.device,
    )
    vector_store = ChromaVectorStore(
        collection_name=context.config.embedding.collection_name,
        embedding_service=embedding_service,
        persist_directory=context.config.embedding.persist_directory,
    )
    vector_store.index_documents(schema_loader.list_documents())
    langchain_retriever = LangChainSchemaRetriever(
        vector_store=vector_store,
        default_top_k=context.config.embedding.top_k,
    )

    intent_agent = IntentAgent("intent_agent", llm=llm, prompt_loader=prompt_loader)
    schema_agent = SchemaAgent(
        "schema_agent",
        retriever=langchain_retriever,
        top_k=context.config.embedding.top_k,
    )
    prompt_builder_agent = PromptBuilderAgent(
        "prompt_builder_agent",
        prompt_loader=prompt_loader,
        prompt_versions=runtime.prompt_versions,
    )
    sql_agent = SQLAgent("sql_agent", llm=llm, prompt_loader=prompt_loader)
    validation_agent = ValidationAgent("validation_agent")
    execution_agent = ExecutionAgent(
        "execution_agent",
        database_client=OracleDatabaseClient(context.config.oracle),
    )
    summary_agent = SummaryAgent("summary_agent", llm=llm, prompt_loader=prompt_loader)

    workflow = build_workflow(
        intent_agent=intent_agent,
        schema_agent=schema_agent,
        prompt_builder_agent=prompt_builder_agent,
        sql_agent=sql_agent,
        validation_agent=validation_agent,
        execution_agent=execution_agent,
        summary_agent=summary_agent,
        runtime=runtime,
        max_validation_retries=context.config.runtime.sql_validation_retries,
    )

    initial_state = ERPAgentState(
        user_question=question.strip(),
        session_id=f"session-{uuid4()}",
    )
    return execute_workflow(workflow, initial_state, runtime)
