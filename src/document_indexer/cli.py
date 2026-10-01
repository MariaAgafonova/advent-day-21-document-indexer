import argparse
import json
import sys
from pathlib import Path

def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Document Indexer — локальный семантический поиск")
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect", help="Статистика локального корпуса")
    inspect.add_argument("--input", default="data/raw")
    inspect.add_argument("--output", default="output/corpus_stats.json")
    inspect.add_argument("--tokens", action="store_true", help="Посчитать токены (требуется модель)")
    index = commands.add_parser("index", help="Построить индекс")
    index.add_argument("--input", default="data/raw")
    index.add_argument("--strategy", choices=["fixed", "structural"], required=True)
    index.add_argument("--output", required=True)
    index.add_argument("--chunk-size", type=int, default=300)
    index.add_argument("--overlap", type=int, default=50)
    index.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    search = commands.add_parser("search", help="Поиск по сохранённой базе")
    search.add_argument("--index", required=True)
    search.add_argument("--query", required=True)
    search.add_argument("--top-k", type=int, default=5)
    search.add_argument("--source")
    compare = commands.add_parser("compare", help="Оценить два индекса и экспортировать отчёт")
    compare.add_argument("--fixed", required=True)
    compare.add_argument("--structural", required=True)
    compare.add_argument("--questions", required=True)
    compare.add_argument("--output", required=True)
    compare.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args(argv)
    def progress(stage, done=0, total=None):
        print(f"{stage}: {done}" + (f" / {total}" if total is not None else ""), file=sys.stderr, flush=True)
    try:
        if args.command == "inspect":
            from .loaders import load_corpus, corpus_stats
            from .embeddings import get_embedding_service
            documents, errors = load_corpus(args.input)
            result = corpus_stats(documents, errors, get_embedding_service().tokenization if args.tokens else None)
            path = Path(args.output)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        elif args.command == "index":
            from .indexing import build_index
            result = build_index(args.input, args.strategy, args.output, args.chunk_size, args.overlap, args.device, progress=progress)
        elif args.command == "search":
            from .storage import load_index
            from .search import search as run_search
            result = run_search(load_index(args.index), args.query, args.top_k, args.source)
        else:
            from .evaluate import compare_files
            from .reporting import export_report
            result = compare_files(args.fixed, args.structural, args.questions, args.repeats, progress)
            export_report(result, args.output)
            result = {key: r["metrics"] for key, r in result["strategies"].items()}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
