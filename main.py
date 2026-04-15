import argparse
from agent.computer_use_agent import AgentConfig, ComputerUseAgent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Operon computer-use agent")
    parser.add_argument(
        "instruction",
        type=str,
        nargs="?",
        default="",
        help="Natural language instruction for the agent",
    )
    parser.add_argument(
        "--max-iterations", type=int, default=15, help="Maximum agent iterations"
    )
    parser.add_argument(
        "--scale", type=float, default=0.6, help="Screenshot scale factor (0.1-1.0)"
    )
    parser.add_argument(
        "--no-verify", action="store_true", help="Skip action verification"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if not args.instruction:
            parser.print_help()
            return 1

        print("Starting computer-use agent...")
        config = AgentConfig(
            max_iterations=args.max_iterations,
            scale=args.scale,
            verify_actions=not args.no_verify,
        )
        agent = ComputerUseAgent(config)
        success, steps = agent.run(args.instruction)
        if success:
            print("Task run finished.")
        else:
            print("Stopped after max iterations.")
        print(f"Steps executed: {len(steps)}")
        return 0

    except KeyboardInterrupt:
        print("Stopped by user.")
        return 0
    except Exception as exc:
        print(f"Run failed: {exc}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
