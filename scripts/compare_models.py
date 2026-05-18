#!/usr/bin/env python3
"""Generate a model comparison document.

Runs every Text Refiner mode at three complexity levels against the
Anthropic Haiku 4.5 and Sonnet 4.6 models, then writes the results to
docs/model-comparison.md so the two models can be compared side by side.
"""

from __future__ import annotations

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import anthropic

from refiner.llm import get_api_key
from refiner.prompts import PROMPTS, MODE_NAMES

MODELS = [
    ("Haiku 4.5", "claude-haiku-4-5-20251001"),
    ("Sonnet 4.6", "claude-sonnet-4-6"),
]

# Order modes how they appear in the picker.
MODE_ORDER = [1, 2, 3, 4, 5, 7]

COMPLEXITY_LABELS = ["simple", "medium", "complex"]


@dataclass(frozen=True)
class Example:
    label: str
    text: str


# Hand-built examples per mode. Medium for Improve Prompt is the user's own
# example from the chat, kept verbatim.
EXAMPLES: dict[int, list[Example]] = {
    1: [  # Clean Up
        Example(
            "simple",
            "um yeah so like i think we should probably maybe go with the "
            "second option you know",
        ),
        Example(
            "medium",
            "ok so we tested the new checkout feature and uh, users seemed "
            "to like it i think? like the metrics looked good and people "
            "were actually using it on the dashboard but theres still some "
            "weird bugs with the loading thing that we need to fix before "
            "we like ship it more widely you know",
        ),
        Example(
            "complex",
            "so basically what happened is, we did the migration this morning "
            "and it kinda worked but kinda didn't. like the data moved over "
            "fine for most of the customers, like 95 percent or whatever, but "
            "then there were these edge cases, you know, where people had "
            "like really old accounts from like 2017 or before, and those "
            "accounts had this weird schema thing where the country field "
            "was stored as an integer instead of a string, and our migration "
            "script just kinda skipped them. and then on top of that, the "
            "billing team noticed that some subscriptions got duplicated, "
            "like literally same user paying twice, which is, you know, "
            "really bad, and we need to figure out by tomorrow if we should "
            "just roll back the whole thing or try to patch forward",
        ),
    ],
    2: [  # Slack
        Example(
            "simple",
            "Please let me know when you have a moment to discuss the "
            "deployment.",
        ),
        Example(
            "medium",
            "Hi team, I wanted to give everyone an update on the API "
            "migration. We finished the staging tests, found two issues "
            "with the rate limiter, and would like to discuss tomorrow "
            "whether we should delay the production rollout.",
        ),
        Example(
            "complex",
            "Hello everyone, I am writing to share several updates from the "
            "platform team. First, the new authentication service is now "
            "running in staging and we are seeing the expected latency "
            "improvements, approximately 40% faster than the legacy "
            "service. Second, we identified a bug in the session refresh "
            "flow which causes users to be logged out after 15 minutes "
            "instead of the configured 24 hours, and we have a fix in "
            "review. Third, we would like to propose a maintenance window "
            "next Thursday evening to perform the database migration, and "
            "would appreciate sign-off from the on-call rotation. Please "
            "let me know if you have any questions or concerns.",
        ),
    ],
    3: [  # Email
        Example(
            "simple",
            "Thanks for the call yesterday. Want to follow up about next "
            "steps for the partnership.",
        ),
        Example(
            "medium",
            "Following up on our discussion about the integration timeline. "
            "Can we schedule a brief sync next week to align on milestones "
            "and confirm the resourcing plan? I would also like to share a "
            "draft of the technical spec so we can review it together "
            "before we kick off implementation.",
        ),
        Example(
            "complex",
            "I wanted to follow up on our conversation last Thursday "
            "regarding the proposed partnership and the open questions we "
            "left on the table. After reviewing internally, we are aligned "
            "on the high level shape of the deal but there are three areas "
            "I would like to clarify before we move to a term sheet. "
            "First, the exclusivity scope: we are happy with category "
            "exclusivity in fintech but cannot commit to broader market "
            "exclusivity in this phase. Second, the integration timeline: "
            "we can commit to a v1 integration in eight weeks if we get "
            "API access by next Monday, otherwise we will need to push by "
            "the equivalent number of days. Third, the revenue share: we "
            "would prefer a tiered model rather than a flat percentage, "
            "and I have attached a one pager outlining what we have in "
            "mind. Could we get on a call this week to walk through these "
            "and see if we can lock the deal shape by end of month?",
        ),
    ],
    4: [  # Report
        Example(
            "simple",
            "We tested the new checkout flow with 500 users last week. "
            "Conversions went up 12%. Recommend rolling out to all users.",
        ),
        Example(
            "medium",
            "We ran a two week experiment comparing the new onboarding "
            "flow against the existing one. Sign ups completed within 24 "
            "hours rose from 38% to 52%. The biggest gain came from "
            "removing the email verification step, which alone accounted "
            "for about two thirds of the improvement. There is a risk "
            "that bot signups will increase, and our spam metrics will "
            "need to be watched. We recommend rolling the change out to "
            "all new users next sprint, with the spam detection threshold "
            "tightened by 10%.",
        ),
        Example(
            "complex",
            "Over the past six weeks we conducted a qualitative and "
            "quantitative study of customer churn across the SMB segment. "
            "Quantitatively, monthly churn for accounts under $200 ARR "
            "was 7.2%, more than double the rate of accounts above $1k "
            "ARR, which sat at 3.1%. Qualitatively, in 22 customer "
            "interviews three themes dominated: 1) the product was hard "
            "to set up without dedicated engineering time, 2) the pricing "
            "felt steep relative to a single use case, and 3) customer "
            "support response times had slipped to over 24 hours, which "
            "small teams found unacceptable. The most striking finding "
            "was that churned customers who had a successful onboarding "
            "call had a churn rate of only 2.4%, suggesting that "
            "investment in white glove onboarding for the SMB segment "
            "could materially reduce churn. Risks include the cost of "
            "scaling onboarding and the possibility of cannibalising "
            "self serve revenue. We recommend a six week pilot of "
            "white glove onboarding for new SMB accounts, with a "
            "success threshold of cutting 90 day churn by at least 30%.",
        ),
    ],
    5: [  # Bullet Points
        Example(
            "simple",
            "I need to buy groceries, go to the gym, and finish the "
            "quarterly report by Friday.",
        ),
        Example(
            "medium",
            "The launch checklist still has a few open items. We need to "
            "finalise the press release with comms, set up the analytics "
            "dashboards for the new feature, brief the support team on "
            "expected questions, run a smoke test of the upgrade path for "
            "existing customers, and confirm the marketing site copy with "
            "legal before publication.",
        ),
        Example(
            "complex",
            "Reflecting on the quarter, several things stood out. The "
            "team delivered the platform migration on schedule despite "
            "two members being on extended leave, which we should "
            "celebrate. Customer satisfaction scores improved slightly "
            "but support volume also grew, suggesting more users overall "
            "rather than higher per user satisfaction. The new pricing "
            "experiment showed that the mid tier converts noticeably "
            "better when we frame it as the popular choice, even though "
            "the underlying value did not change. We had two production "
            "incidents, both caused by missing database indexes after "
            "schema changes, and the postmortems suggest we need a "
            "review step in the migration workflow. Hiring slowed because "
            "the offer process is bottlenecked at compensation approvals "
            "and we lost two strong candidates. Finally, the team morale "
            "survey was positive overall but the engineering org "
            "highlighted lack of focus time as a recurring concern.",
        ),
    ],
    7: [  # Improve Prompt
        Example(
            "simple",
            "write me a marketing email",
        ),
        Example(
            "medium",
            "cool. can you create a very clear and thorough spec to make "
            "this a github app that anyone can install. and it needs an "
            "interface with the default options configurable and more "
            "options able to be added (with things such as 'cancel' not "
            "able to be changed. and we also need like a cool little "
            "loading thingy (light and simple but elegant and modern) and "
            "also have a place where a user can put in their anthropic or "
            "openai or kimi k or gemini api key to use it with the 'slug' "
            "for their model. though give a drop down with the primary "
            "models as options for the given provider such as anthropic "
            "etc.",
        ),
        Example(
            "complex",
            "so im thinking about building this thing where you can like "
            "throw any messy notes or transcripts into it and it spits "
            "out really clean structured docs, kinda like notion but "
            "smarter and more opinionated, and ideally it should learn "
            "the user's style over time so it doesn't always sound "
            "generic, also has to handle like meeting notes and personal "
            "journaling and project planning all in the same place, and "
            "it should probably integrate with stuff like slack and "
            "calendar and email so it can pull context automatically and "
            "be proactive about suggesting things to follow up on, oh and "
            "the design needs to feel calm and minimal not crammed with "
            "features, and it should work great offline too because "
            "people travel, and pricing should be a free tier plus a "
            "subscription, dont know what to charge yet, and i want to "
            "be able to white label it later for enterprise customers, "
            "i guess i need help shaping this into an actual prompt for "
            "an LLM to help me plan it out properly without it just "
            "hallucinating a whole product spec",
        ),
    ],
}


def call_model(model_id: str, system_prompt: str, user_text: str) -> str:
    client = anthropic.Anthropic(api_key=get_api_key())
    response = client.messages.create(
        model=model_id,
        max_tokens=1500,
        system=system_prompt,
        messages=[{"role": "user", "content": user_text}],
        timeout=60,
    )
    return response.content[0].text


def run_one(mode: int, example_idx: int, model_label: str, model_id: str) -> tuple:
    system_prompt = PROMPTS[mode]
    example = EXAMPLES[mode][example_idx]
    start = time.monotonic()
    try:
        text = call_model(model_id, system_prompt, example.text)
        elapsed = time.monotonic() - start
        return (mode, example_idx, model_label, text, elapsed, None)
    except Exception as exc:
        elapsed = time.monotonic() - start
        return (mode, example_idx, model_label, "", elapsed, str(exc))


def main() -> int:
    tasks = []
    for mode in MODE_ORDER:
        for example_idx in range(3):
            for model_label, model_id in MODELS:
                tasks.append((mode, example_idx, model_label, model_id))

    results: dict[tuple, tuple] = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        future_to_task = {
            pool.submit(run_one, *task): task for task in tasks
        }
        completed = 0
        for future in as_completed(future_to_task):
            mode, example_idx, model_label, text, elapsed, error = future.result()
            results[(mode, example_idx, model_label)] = (text, elapsed, error)
            completed += 1
            print(
                f"[{completed}/{len(tasks)}] mode={mode} "
                f"complexity={COMPLEXITY_LABELS[example_idx]} "
                f"model={model_label} elapsed={elapsed:.1f}s "
                f"{'OK' if not error else 'ERROR: ' + error}",
                flush=True,
            )

    out_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "docs",
        "model-comparison.md",
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        write_markdown(fh, results)
    print(f"Wrote {out_path}", flush=True)
    return 0


def write_markdown(fh, results: dict) -> None:
    fh.write("# Text Refiner — Model Comparison\n\n")
    fh.write(
        "Side-by-side outputs for every mode at three complexity levels, "
        "comparing Claude Haiku 4.5 against Claude Sonnet 4.6. Use this to "
        "decide which model fits your use case.\n\n"
    )
    fh.write("Models tested:\n\n")
    for label, model_id in MODELS:
        fh.write(f"- **{label}** — `{model_id}`\n")
    fh.write("\n---\n\n")

    for mode in MODE_ORDER:
        mode_name = MODE_NAMES[mode]
        fh.write(f"## {mode}. {mode_name}\n\n")
        for example_idx, example in enumerate(EXAMPLES[mode]):
            fh.write(f"### {example.label.title()}\n\n")
            fh.write("**Input**\n\n")
            fh.write("> " + example.text.replace("\n", "\n> ") + "\n\n")

            for model_label, _ in MODELS:
                text, elapsed, error = results[(mode, example_idx, model_label)]
                fh.write(f"#### {model_label} · {elapsed:.1f}s\n\n")
                if error:
                    fh.write(f"_Error: {error}_\n\n")
                else:
                    fh.write(text.strip() + "\n\n")
            fh.write("---\n\n")


if __name__ == "__main__":
    raise SystemExit(main())
