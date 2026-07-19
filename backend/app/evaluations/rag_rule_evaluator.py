from __future__ import annotations

import math
import re
from statistics import mean
from typing import Any, Dict, List, Optional, Set

from app.evaluations.rag_eval_models import (
    RAGAnswerMetrics,
    RAGEvalCase,
    RAGRetrievalMetrics,
    RAGRuleCheckResult,
)

"""RAG 知识库检索、引用和答案的确定性评估。"""

class RAGRuleEvaluator:
    """使用可审计规则计算 RAG 检索和回答指标。"""

    def evaluate(
        self,
        case: RAGEvalCase,
        answer: str,
        sources: List[Dict[str, Any]],
        context_used: bool,
        query_rewrite: Optional[Dict[str, Any]] = None,
    ) -> tuple[List[RAGRuleCheckResult], RAGRetrievalMetrics, RAGAnswerMetrics]:
        retrieval_metrics = self.compute_retrieval_metrics(case, sources, context_used)
        answer_metrics = self.compute_answer_metrics(case, answer)
        checks = [
            self._check_answer_policy(case, answer, answer_metrics),
            self._check_answer_length(case, answer),
            self._check_forbidden_answer_keywords(answer_metrics),
            self._check_context_used(case, retrieval_metrics),
            self._check_recall(case, retrieval_metrics),
            self._check_precision(case, retrieval_metrics),
            self._check_mrr(case, retrieval_metrics),
            self._check_ndcg(case, retrieval_metrics),
            self._check_citation_accuracy(case, retrieval_metrics),
            self._check_context_keywords(case, retrieval_metrics),
            self._check_query_rewrite(case, query_rewrite or {}),
        ]
        return [check for check in checks if check is not None], retrieval_metrics, answer_metrics

    def aggregate_score(self, checks: List[RAGRuleCheckResult]) -> float:
        if not checks:
            return 0.0
        return round(mean(check.score for check in checks), 4)

    def compute_retrieval_metrics(
        self,
        case: RAGEvalCase,
        sources: List[Dict[str, Any]],
        context_used: bool,
    ) -> RAGRetrievalMetrics:
        k = max(int(case.context_limit or len(sources) or 1), 1)
        limited_sources = sources[:k]
        retrieved_document_ids = [self._source_document_id(source) for source in limited_sources]
        retrieved_document_ids = [item for item in retrieved_document_ids if item]
        retrieved_chunk_refs = [ref for source in limited_sources for ref in self._source_refs(source)]

        expected_refs = self._expected_refs(case)
        source_relevances = [
            self._is_relevant_source(source, expected_refs, case.expected_context_keywords)
            for source in limited_sources
        ]
        relevant_ranks = [index for index, relevant in enumerate(source_relevances, start=1) if relevant]

        recall_at_k: Optional[float] = None
        if expected_refs:
            hit_refs = self._hit_expected_refs(expected_refs, limited_sources)
            recall_at_k = round(len(hit_refs) / max(len(expected_refs), 1), 4)
        elif case.expected_context_keywords:
            recall_at_k = self._context_keyword_recall(case.expected_context_keywords, limited_sources)

        relevant_count = sum(1 for item in source_relevances if item)
        precision_at_k: Optional[float] = None
        hit_rate_at_k: Optional[float] = None
        mrr: Optional[float] = None
        ndcg_at_k: Optional[float] = None
        citation_accuracy: Optional[float] = None

        if expected_refs or case.expected_context_keywords:
            precision_at_k = round(relevant_count / k, 4)
            hit_rate_at_k = 1.0 if relevant_count > 0 else 0.0
            mrr = round(1.0 / relevant_ranks[0], 4) if relevant_ranks else 0.0
            ndcg_at_k = self._ndcg(source_relevances, expected_count=len(expected_refs) or relevant_count, k=k)
            citation_accuracy = (
                round(relevant_count / max(len(limited_sources), 1), 4)
                if limited_sources
                else 0.0
            )

        context_keyword_recall = (
            self._context_keyword_recall(case.expected_context_keywords, limited_sources)
            if case.expected_context_keywords
            else None
        )

        return RAGRetrievalMetrics(
            k=k,
            context_used=context_used,
            num_sources=len(limited_sources),
            retrieved_document_ids=retrieved_document_ids,
            retrieved_chunk_refs=retrieved_chunk_refs,
            relevant_ranks=relevant_ranks,
            recall_at_k=recall_at_k,
            precision_at_k=precision_at_k,
            hit_rate_at_k=hit_rate_at_k,
            mrr=mrr,
            ndcg_at_k=ndcg_at_k,
            citation_accuracy=citation_accuracy,
            context_keyword_recall=context_keyword_recall,
        )

    def compute_answer_metrics(self, case: RAGEvalCase, answer: str) -> RAGAnswerMetrics:
        answer_hit_rate = self._keyword_score(case.expected_answer_keywords, answer)
        forbidden_hits = [
            item
            for item in case.forbidden_answer_keywords
            if self._normalize_text(item) in self._normalize_text(answer)
        ]
        refusal_accuracy: Optional[float] = None
        if not case.should_answer:
            refusal_accuracy = 1.0 if self._contains_any(answer, case.refusal_keywords) else 0.0
        return RAGAnswerMetrics(
            answer_hit_rate=answer_hit_rate,
            forbidden_keyword_hits=forbidden_hits,
            refusal_accuracy=refusal_accuracy,
            answer_length=len(answer.strip()),
        )

    def _check_answer_policy(
        self,
        case: RAGEvalCase,
        answer: str,
        metrics: RAGAnswerMetrics,
    ) -> RAGRuleCheckResult:
        if not case.should_answer:
            passed = bool(metrics.refusal_accuracy)
            return RAGRuleCheckResult(
                name="无答案拒答检查",
                passed=passed,
                score=float(metrics.refusal_accuracy or 0.0),
                reason="无答案问题已正确拒答。" if passed else "无答案问题没有明确拒答，存在编造风险。",
                details={"refusal_keywords": case.refusal_keywords},
            )

        if not case.expected_answer_keywords:
            passed = bool(answer.strip())
            return RAGRuleCheckResult(
                name="答案非空检查",
                passed=passed,
                score=1.0 if passed else 0.0,
                reason="答案非空。" if passed else "RAG 返回答案为空。",
            )

        threshold = case.min_answer_hit_rate if case.min_answer_hit_rate is not None else 1.0
        missing = self._missing_keywords(case.expected_answer_keywords, answer)
        passed = metrics.answer_hit_rate >= threshold
        return RAGRuleCheckResult(
            name="答案命中率检查",
            passed=passed,
            score=metrics.answer_hit_rate,
            reason=(
                f"答案命中率 {metrics.answer_hit_rate:.4f} 达到阈值 {threshold:.4f}。"
                if passed
                else f"答案命中率 {metrics.answer_hit_rate:.4f} 低于阈值 {threshold:.4f}，缺少：{', '.join(missing)}。"
            ),
            details={
                "expected_answer_keywords": case.expected_answer_keywords,
                "missing": missing,
                "threshold": threshold,
            },
        )

    def _check_answer_length(self, case: RAGEvalCase, answer: str) -> RAGRuleCheckResult:
        length = len(answer.strip())
        min_passed = length >= case.min_answer_length
        max_passed = case.max_answer_length is None or length <= case.max_answer_length
        passed = min_passed and max_passed
        if not min_passed:
            score = max(0.0, length / max(case.min_answer_length, 1))
        elif not max_passed:
            score = 0.0
        else:
            score = 1.0
        return RAGRuleCheckResult(
            name="答案长度检查",
            passed=passed,
            score=round(score, 4),
            reason=f"答案长度 {length}，最小 {case.min_answer_length}，最大 {case.max_answer_length or '不限制'}。",
            details={"length": length, "min_answer_length": case.min_answer_length, "max_answer_length": case.max_answer_length},
        )

    def _check_forbidden_answer_keywords(
        self,
        metrics: RAGAnswerMetrics,
    ) -> RAGRuleCheckResult:
        passed = not metrics.forbidden_keyword_hits
        return RAGRuleCheckResult(
            name="答案禁用词检查",
            passed=passed,
            score=1.0 if passed else 0.0,
            reason="未命中答案禁用词。" if passed else f"命中禁用词：{', '.join(metrics.forbidden_keyword_hits)}。",
            details={"hits": metrics.forbidden_keyword_hits},
        )

    def _check_context_used(
        self,
        case: RAGEvalCase,
        metrics: RAGRetrievalMetrics,
    ) -> Optional[RAGRuleCheckResult]:
        if case.expected_context_used is None:
            return None
        passed = metrics.context_used == case.expected_context_used
        return RAGRuleCheckResult(
            name="是否使用知识库上下文检查",
            passed=passed,
            score=1.0 if passed else 0.0,
            reason=(
                f"context_used 符合预期：{metrics.context_used}。"
                if passed
                else f"context_used 不符合预期，期望 {case.expected_context_used}，实际 {metrics.context_used}。"
            ),
            details={"expected": case.expected_context_used, "actual": metrics.context_used},
        )

    def _check_recall(
        self,
        case: RAGEvalCase,
        metrics: RAGRetrievalMetrics,
    ) -> Optional[RAGRuleCheckResult]:
        if metrics.recall_at_k is None:
            return None
        threshold = case.min_recall_at_k if case.min_recall_at_k is not None else 1.0
        passed = metrics.recall_at_k >= threshold
        return RAGRuleCheckResult(
            name=f"Recall@{metrics.k} 检查",
            passed=passed,
            score=metrics.recall_at_k,
            reason=(
                f"Recall@{metrics.k}={metrics.recall_at_k:.4f} 达到阈值 {threshold:.4f}。"
                if passed
                else f"Recall@{metrics.k}={metrics.recall_at_k:.4f} 低于阈值 {threshold:.4f}。"
            ),
            details={"threshold": threshold, "retrieved_chunk_refs": metrics.retrieved_chunk_refs},
        )

    def _check_precision(
        self,
        case: RAGEvalCase,
        metrics: RAGRetrievalMetrics,
    ) -> Optional[RAGRuleCheckResult]:
        if metrics.precision_at_k is None:
            return None
        threshold = case.min_precision_at_k if case.min_precision_at_k is not None else 0.0
        passed = metrics.precision_at_k >= threshold
        return RAGRuleCheckResult(
            name=f"Precision@{metrics.k} 检查",
            passed=passed,
            score=metrics.precision_at_k,
            reason=f"Precision@{metrics.k}={metrics.precision_at_k:.4f}，阈值 {threshold:.4f}。",
            details={"threshold": threshold, "relevant_ranks": metrics.relevant_ranks},
        )

    def _check_mrr(
        self,
        case: RAGEvalCase,
        metrics: RAGRetrievalMetrics,
    ) -> Optional[RAGRuleCheckResult]:
        if metrics.mrr is None:
            return None
        threshold = case.min_mrr if case.min_mrr is not None else 0.0
        passed = metrics.mrr >= threshold
        return RAGRuleCheckResult(
            name="MRR 检查",
            passed=passed,
            score=metrics.mrr,
            reason=f"MRR={metrics.mrr:.4f}，阈值 {threshold:.4f}。",
            details={"threshold": threshold, "relevant_ranks": metrics.relevant_ranks},
        )

    def _check_ndcg(
        self,
        case: RAGEvalCase,
        metrics: RAGRetrievalMetrics,
    ) -> Optional[RAGRuleCheckResult]:
        if metrics.ndcg_at_k is None:
            return None
        threshold = case.min_ndcg_at_k if case.min_ndcg_at_k is not None else 0.0
        passed = metrics.ndcg_at_k >= threshold
        return RAGRuleCheckResult(
            name=f"NDCG@{metrics.k} 检查",
            passed=passed,
            score=metrics.ndcg_at_k,
            reason=f"NDCG@{metrics.k}={metrics.ndcg_at_k:.4f}，阈值 {threshold:.4f}。",
            details={"threshold": threshold},
        )

    def _check_citation_accuracy(
        self,
        case: RAGEvalCase,
        metrics: RAGRetrievalMetrics,
    ) -> Optional[RAGRuleCheckResult]:
        if metrics.citation_accuracy is None:
            return None
        threshold = case.min_citation_accuracy if case.min_citation_accuracy is not None else 0.0
        passed = metrics.citation_accuracy >= threshold
        return RAGRuleCheckResult(
            name="引用来源正确率检查",
            passed=passed,
            score=metrics.citation_accuracy,
            reason=f"引用来源正确率={metrics.citation_accuracy:.4f}，阈值 {threshold:.4f}。",
            details={
                "threshold": threshold,
                "retrieved_document_ids": metrics.retrieved_document_ids,
                "retrieved_chunk_refs": metrics.retrieved_chunk_refs,
            },
        )

    def _check_context_keywords(
        self,
        case: RAGEvalCase,
        metrics: RAGRetrievalMetrics,
    ) -> Optional[RAGRuleCheckResult]:
        if metrics.context_keyword_recall is None:
            return None
        threshold = case.min_context_keyword_recall if case.min_context_keyword_recall is not None else 1.0
        passed = metrics.context_keyword_recall >= threshold
        return RAGRuleCheckResult(
            name="检索上下文关键词召回检查",
            passed=passed,
            score=metrics.context_keyword_recall,
            reason=f"上下文关键词召回={metrics.context_keyword_recall:.4f}，阈值 {threshold:.4f}。",
            details={"expected_context_keywords": case.expected_context_keywords, "threshold": threshold},
        )

    def _check_query_rewrite(
        self,
        case: RAGEvalCase,
        query_rewrite: Dict[str, Any],
    ) -> Optional[RAGRuleCheckResult]:
        if not case.expected_query_keywords:
            return None
        rewritten_query = str(query_rewrite.get("rewritten_query") or "")
        expanded_keywords = " ".join(str(item) for item in query_rewrite.get("expanded_keywords") or [])
        combined = f"{rewritten_query} {expanded_keywords}"
        missing = self._missing_keywords(case.expected_query_keywords, combined)
        passed = not missing
        score = self._keyword_score(case.expected_query_keywords, combined)
        return RAGRuleCheckResult(
            name="查询改写关键词检查",
            passed=passed,
            score=score,
            reason="查询改写关键词全部命中。" if passed else f"查询改写缺少关键词：{', '.join(missing)}。",
            details={"query_rewrite": query_rewrite, "missing": missing},
        )

    def _expected_refs(self, case: RAGEvalCase) -> Set[str]:
        refs = {str(item) for item in case.expected_document_ids if str(item).strip()}
        refs.update(str(item) for item in case.expected_chunk_refs if str(item).strip())
        return refs

    def _hit_expected_refs(self, expected_refs: Set[str], sources: List[Dict[str, Any]]) -> Set[str]:
        hits: Set[str] = set()
        for source in sources:
            source_refs = set(self._source_refs(source))
            for expected in expected_refs:
                if expected in source_refs:
                    hits.add(expected)
        return hits

    def _is_relevant_source(
        self,
        source: Dict[str, Any],
        expected_refs: Set[str],
        context_keywords: List[str],
    ) -> bool:
        if expected_refs and expected_refs.intersection(set(self._source_refs(source))):
            return True
        if context_keywords:
            content = str(source.get("content") or "")
            return any(self._normalize_text(keyword) in self._normalize_text(content) for keyword in context_keywords)
        return False

    def _source_refs(self, source: Dict[str, Any]) -> List[str]:
        refs: List[str] = []
        document_id = self._source_document_id(source)
        chunk_index = source.get("chunk_index")
        chunk_id = source.get("chunk_id")
        if document_id:
            refs.append(document_id)
            if chunk_index is not None:
                refs.append(f"{document_id}#{chunk_index}")
        if chunk_id:
            refs.append(f"chunk_id:{chunk_id}")
            refs.append(str(chunk_id))
        metadata = source.get("metadata") or {}
        if isinstance(metadata, dict):
            meta_doc_id = str(metadata.get("document_id") or "").strip()
            meta_chunk_index = metadata.get("chunk_index")
            meta_chunk_id = str(metadata.get("chunk_id") or "").strip()
            if meta_doc_id and meta_doc_id not in refs:
                refs.append(meta_doc_id)
            if meta_doc_id and meta_chunk_index is not None:
                refs.append(f"{meta_doc_id}#{meta_chunk_index}")
            if meta_chunk_id:
                refs.extend([f"chunk_id:{meta_chunk_id}", meta_chunk_id])
        return [ref for ref in refs if ref]

    def _source_document_id(self, source: Dict[str, Any]) -> str:
        document_id = str(source.get("document_id") or "").strip()
        if document_id:
            return document_id
        metadata = source.get("metadata") or {}
        if isinstance(metadata, dict):
            return str(metadata.get("document_id") or "").strip()
        return ""

    def _context_keyword_recall(self, keywords: List[str], sources: List[Dict[str, Any]]) -> Optional[float]:
        if not keywords:
            return None
        contexts = "\n".join(str(source.get("content") or "") for source in sources)
        return self._keyword_score(keywords, contexts)

    def _keyword_score(self, keywords: List[str], text: str) -> float:
        if not keywords:
            return 1.0
        missing = self._missing_keywords(keywords, text)
        return round((len(keywords) - len(missing)) / max(len(keywords), 1), 4)

    def _missing_keywords(self, keywords: List[str], text: str) -> List[str]:
        normalized_text = self._normalize_text(text)
        return [
            keyword
            for keyword in keywords
            if self._normalize_text(keyword) not in normalized_text
        ]

    def _contains_any(self, text: str, keywords: List[str]) -> bool:
        normalized_text = self._normalize_text(text)
        return any(self._normalize_text(keyword) in normalized_text for keyword in keywords)

    def _ndcg(self, relevances: List[bool], expected_count: int, k: int) -> Optional[float]:
        if not relevances and expected_count <= 0:
            return None
        dcg = 0.0
        for index, relevant in enumerate(relevances[:k], start=1):
            if relevant:
                dcg += 1.0 / math.log2(index + 1)
        ideal_hits = min(max(expected_count, sum(1 for item in relevances if item)), k)
        if ideal_hits <= 0:
            return 0.0
        idcg = sum(1.0 / math.log2(index + 1) for index in range(1, ideal_hits + 1))
        return round(dcg / idcg, 4) if idcg else 0.0

    def _normalize_text(self, text: Any) -> str:
        return re.sub(r"\s+", "", str(text or "")).lower()
