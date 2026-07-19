
from __future__ import annotations

import argparse
import asyncio
import shutil
import sys
from datetime import datetime
from pathlib import Path

"""运行 RAG 知识库固定问答评估集。"""

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.evaluations.rag_eval_runner import (
    RAGEvalRunner,
    load_rag_eval_cases,
    write_rag_json_report,
    write_rag_markdown_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="运行 RAG 知识库评估。",
        add_help=False,
        usage="python scripts/run_rag_evals.py [选项]",
    )
    parser._optionals.title = "选项"
    parser.add_argument("-h", "--help", action="help", help="显示帮助信息并退出。")
    parser.add_argument(
        "--cases",
        type=Path,
        metavar="样例路径",
        default=BACKEND_DIR / "evals" / "rag_cases",
        help="JSON 评估样例文件路径，或包含多个 JSON 评估样例文件的目录。",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        metavar="报告目录",
        default=BACKEND_DIR / "evals" / "reports",
        help="JSON 和 Markdown 评估报告的输出目录。",
    )
    parser.add_argument("--repeat-runs", type=int, default=3, metavar="次数", help="每条样例重复运行次数。")
    parser.add_argument("--concurrency", type=int, default=1, metavar="数量", help="并发执行的样例数量。")
    parser.add_argument("--ragas", action="store_true", help="启用 RAGAS 指标评估。")
    parser.add_argument("--baseline", type=Path, default=None, metavar="基线报告", help="用于回归对比的历史 JSON 报告路径。")
    parser.add_argument("--fail-on-regression", action="store_true", help="如果核心指标回退，则以非零状态码退出。")
    parser.add_argument("--fail-on-failed-cases", action="store_true", help="如果存在失败样例，则以非零状态码退出。")
    return parser.parse_args()


async def main() -> int:
    args = parse_args()

    # 获取评估集
    cases_path = args.cases if args.cases.is_absolute() else BACKEND_DIR / args.cases
    output_dir = args.output_dir if args.output_dir.is_absolute() else BACKEND_DIR / args.output_dir
    baseline_path = None
    if args.baseline:
        baseline_path = args.baseline if args.baseline.is_absolute() else BACKEND_DIR / args.baseline

    cases = load_rag_eval_cases(cases_path)
    if not cases:
        print(f"未读取到 RAG 评估样例: {cases_path}")
        return 2

    print(f"读取 RAG 评估样例: {len(cases)} 条")
    print(f"重复运行次数: {args.repeat_runs}")
    print(f"RAGAS: {'启用' if args.ragas else '关闭'}")

    # 开始评估
    runner = RAGEvalRunner()
    report = await runner.run(
        cases=cases,
        repeat_runs=args.repeat_runs,
        concurrency=args.concurrency,
        use_ragas=args.ragas,
        baseline_path=baseline_path,
    )

    # 存储报告
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"rag_eval_{timestamp}.json"
    md_path = output_dir / f"rag_eval_{timestamp}.md"
    latest_json_path = output_dir / "rag_eval_latest.json"
    latest_md_path = output_dir / "rag_eval_latest.md"
    write_rag_json_report(report, json_path)
    write_rag_markdown_report(report, md_path)
    shutil.copyfile(json_path, latest_json_path)
    shutil.copyfile(md_path, latest_md_path)

    print("")
    print("=== RAG 评估完成 ===")
    print(f"总样例: {report.total_cases}")
    print(f"通过: {report.passed_cases}")
    print(f"失败: {report.failed_cases}")
    print(f"通过率: {report.pass_rate:.2%}")
    print(f"规则平均分: {report.average_rule_score:.4f}")
    print(f"Recall@K: {_format_optional(report.average_recall_at_k)}")
    print(f"Precision@K: {_format_optional(report.average_precision_at_k)}")
    print(f"HitRate@K: {_format_optional(report.average_hit_rate_at_k)}")
    print(f"MRR: {_format_optional(report.average_mrr)}")
    print(f"NDCG@K: {_format_optional(report.average_ndcg_at_k)}")
    print(f"引用来源正确率: {_format_optional(report.average_citation_accuracy)}")
    print(f"上下文关键词召回率: {_format_optional(report.average_context_keyword_recall)}")
    print(f"答案命中率: {report.average_answer_hit_rate:.4f}")
    print(f"拒答正确率: {_format_optional(report.average_refusal_accuracy)}")
    print(f"平均延迟: {report.average_latency_ms:.2f} ms")

    if report.ragas.enabled:
        print("")
        print("=== RAGAS ===")
        if report.ragas.error:
            print(f"RAGAS 执行失败: {report.ragas.error}")
        else:
            for key, value in report.ragas.scores.items():
                print(f"{key}: {value:.4f}")
            for key in report.ragas.failed_metrics:
                print(f"{key}: 计算失败（请查看上方 Job 异常）")

    if report.regression:
        print("")
        print("=== 回归对比 ===")
        print(f"基线: {report.regression.baseline_path}")
        print(f"通过率变化: {report.regression.pass_rate_delta}")
        print(f"Recall@K 变化: {report.regression.recall_at_k_delta}")
        print(f"MRR 变化: {report.regression.mrr_delta}")
        print(f"引用来源正确率变化: {report.regression.citation_accuracy_delta}")
        print(f"答案命中率变化: {report.regression.answer_hit_rate_delta}")
    print("")
    print(f"JSON 报告: {json_path}")
    print(f"Markdown 报告: {md_path}")

    if args.fail_on_failed_cases and report.failed_cases:
        return 1
    if args.fail_on_regression and report.regression:
        deltas = [
            report.regression.pass_rate_delta,
            report.regression.recall_at_k_delta,
            report.regression.mrr_delta,
            report.regression.citation_accuracy_delta,
            report.regression.answer_hit_rate_delta,
        ]
        if any((delta or 0) < 0 for delta in deltas):
            return 1
    return 0


def _format_optional(value: float | None) -> str:
    return "未配置" if value is None else f"{value:.4f}"


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
