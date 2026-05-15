import os
from openai import OpenAI

# ─────────────────────────────────────────────
# 1. Initialize NVIDIA Client
# ─────────────────────────────────────────────
client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key="xxxxx"  # Replace with your actual NVIDIA API key
)

# ─────────────────────────────────────────────
# 2. Configuration
# ─────────────────────────────────────────────
INPUT_DIR  = "path/to/your/transcript/folder"   # Folder containing .txt transcript files
OUTPUT_DIR = "path/to/your/output/folder"       # Where .md files will be saved
MODEL      = "meta/llama-3.3-70b-instruct"      # NVIDIA NIM model (can be swapped)

# ─────────────────────────────────────────────
# 3. Prompts
# ─────────────────────────────────────────────

SYSTEM_PROMPT = (
    "You are a Senior SOC Analyst and technical writer. Your task is to convert a raw "
    "lecture transcript into a highly structured, professional Markdown study guide.\n\n"

    "STRICT RULES (FAILURE IS NOT AN OPTION):\n"
    "1. ZERO OUTSIDE KNOWLEDGE: You must ONLY use information explicitly stated in the "
    "transcript. If the instructor defines a tool or flag (e.g., tcpdump -t) differently "
    "than standard documentation, you MUST document the instructor's exact definition. "
    "Do not autocorrect facts. If a value (IP address, filename, port) is unclear or "
    "garbled in the transcript, document it exactly as heard and append [transcription "
    "unclear] — do NOT substitute a plausible value from your training data.\n"
    "2. COMPREHENSIVENESS: Do not aggressively summarize. If the instructor lists multiple "
    "details, use cases, or historical context for a port, protocol, or tool, capture ALL "
    "of them in full.\n"
    "3. TRANSCRIPTION CORRECTIONS — MANDATORY: You MUST silently correct the following "
    "known speech-to-text errors. If any appear uncorrected in your output, your output "
    "is invalid:\n"
    "   - 'cobalt stripe'          -> Cobalt Strike\n"
    "   - 'Sierra cotta'           -> Suricata\n"
    "   - 'cilk' or 'silk'         -> SiLK\n"
    "   - 'etsy host' / 'etsy hosts' -> /etc/hosts\n"
    "   - 'first dash opportunity dot online' -> first-opportunity.online\n"
    "   Apply the same logic to any other well-known tool, malware family, or domain name "
    "that is clearly a phonetic transcription error.\n"
    "4. FALSE FLAGS: Do not confuse network interface names (e.g., enp0s3, eth0, lo) with "
    "CLI flags. Interface names are NEVER flags.\n"
    "5. NO OUTSIDE KNOWLEDGE IN TABLES: If a section has nothing to document, write "
    "'None mentioned.' Do NOT populate tables with ports, protocols, or flags from your "
    "training data that were not stated in this transcript. A note saying 'commonly "
    "relevant' does NOT make outside knowledge acceptable.\n"
    "6. ANALOGY ATTRIBUTION: Only document a teaching analogy under the specific lesson "
    "where the instructor uses it. Do not carry analogies forward into other lessons.\n"
    "7. FLAG TABLE SEPARATION: If a lesson uses multiple tools (e.g., tcpdump AND grep), "
    "create a SEPARATE clearly labelled sub-table for EACH tool's flags. Never mix flags "
    "from different tools in the same table.\n"
    "8. IOC DEDUPLICATION: Each IOC must appear only once in the IOC table. Before "
    "finalising, check for and remove duplicate rows.\n\n"

    "OUTPUT STRUCTURE:\n\n"

    "### 1. Course Objectives & Core Concepts\n"
    "List the specific learning objectives if mentioned (e.g., in intro videos). Explain "
    "the theoretical 'why' behind the topic. CRITICAL: You MUST capture any teaching "
    "analogies the instructor uses (e.g., 'like a phone bill') and attribute them to this "
    "lesson only if stated here. Capture all alternative protocols mentioned.\n\n"

    "### 2. Ports, Protocols & Key Values\n"
    "If the transcript enumerates ports, protocols, flags, or any reference list, render "
    "them as a Markdown table. Do NOT summarise into prose. Use this format:\n"
    "| Port | Protocol | Notes |\n"
    "|------|----------|---------|\n"
    "| 22   | SSH      | Encrypted remote access. Can integrate SFTP. |\n"
    "CRITICAL: The Notes column MUST be comprehensive. Include every specific use case, "
    "vulnerability, security implication, and Windows/Linux context mentioned by the "
    "instructor for each port. If nothing was mentioned, write 'None mentioned.'\n\n"

    "### 3. Command-line Syntax\n"
    "Extract every CLI command or script mentioned. Document the exact syntax in fenced "
    "code blocks. If only the command name is mentioned without full syntax, document the "
    "name and its stated purpose.\n\n"

    "### 4. Tools & Infrastructure\n"
    "Document every tool, appliance, or data collection method mentioned "
    "(e.g., Wireshark, network taps, SPAN ports, NetFlow collectors). Include the purpose "
    "of each as described by the instructor. Do not include flags here — those go in "
    "Section 5.\n\n"

    "### 5. Flags, Settings & Configurations\n"
    "ONLY include flags explicitly stated as flags (i.e., they begin with - or --). "
    "Network interface names are NEVER flags. If a lesson covers multiple tools, create "
    "a separate labelled sub-table per tool. Use this format:\n"
    "| Flag | Effect |\n"
    "|------|--------|\n"
    "| -n   | Suppress DNS resolution |\n\n"

    "### 6. Analyst Tips & IR Methodology\n"
    "Document all pro-tips, best practices, and warnings stated by the instructor. "
    "CRITICAL: If the instructor describes a step-by-step investigation or IR methodology, "
    "you MUST format it as a numbered list (1, 2, 3...) that preserves the exact sequence "
    "of steps as stated.\n\n"

    "### 7. IOCs & Forensic Artifacts\n"
    "Capture all IP addresses, domains, URLs, file names, string signatures "
    "(e.g., 'This program cannot be run in DOS mode'), user agents, and malware family "
    "names. Present as a table with no duplicate rows. Use this format:\n"
    "| IOC / Artifact | Type | Description |\n"
    "|----------------|------|-------------|\n\n"

    "Keep language technical and concise. Ensure no detail from the transcript is left "
    "behind."
)

VALIDATION_PROMPT = (
    "You are a strict QA reviewer for SOC analyst study notes.\n\n"
    "You will be given a raw lecture transcript and a set of study notes generated from "
    "it. Your ONLY job is to identify what is MISSING or INCORRECT in the notes compared "
    "to the transcript. Be specific and exhaustive.\n\n"
    "First, silently extract a list of all technical tools, commands, flags, analogies, "
    "ports, protocols, IOCs, forensic artifacts, and specific facts mentioned in the "
    "transcript. Then, verify if each one exists in the generated notes. Use this internal "
    "checklist to drive your gap analysis before producing your output.\n\n"

    "CHECK FOR ALL OF THE FOLLOWING:\n"
    "1. Any concept, analogy, tool, command, flag, IOC, or forensic artifact present in "
    "the transcript that is completely absent from the notes.\n"
    "2. Any fact in the notes that contradicts what the instructor stated in the "
    "transcript (e.g., a flag described incorrectly).\n"
    "3. Flags from one tool (e.g., grep) placed inside another tool's flag table "
    "(e.g., tcpdump).\n"
    "4. Any content in the notes that does NOT appear in the transcript — i.e., outside "
    "knowledge added by the model (e.g., ports not mentioned in this transcript).\n"
    "5. Uncorrected transcription errors: 'cobalt stripe', 'Sierra cotta', 'Cilk', "
    "'Etsy host', or any garbled tool/malware name that was not fixed.\n"
    "6. Duplicate rows in the IOC table.\n"
    "7. A teaching analogy attributed to the wrong lesson (i.e., mentioned in the notes "
    "but not actually used by the instructor in this transcript).\n"
    "8. An IP address, domain, or filename that was garbled in the transcript but was "
    "silently 'corrected' to a plausible value in the notes without a "
    "[transcription unclear] note.\n\n"

    "OUTPUT FORMAT:\n"
    "Return ONLY a bullet-point list of specific, actionable gaps or errors found.\n"
    "Each bullet must reference the specific section (e.g., 'Section 5', 'IOC table') "
    "and the specific content that is wrong or missing.\n"
    "If the notes are complete and accurate, return exactly: "
    "'VALIDATION PASSED - No gaps found.'\n"
    "Do NOT rewrite or improve the notes. Only report issues."
)

FIX_PROMPT = (
    "You are given a set of study notes, the original lecture transcript they were "
    "generated from, and a QA report listing specific gaps and errors in the notes.\n\n"
    "Your job is to produce a corrected version of the notes that fixes ONLY the issues "
    "listed in the QA report. Do not change, reformat, or 'improve' any section that is "
    "not mentioned in the QA report.\n\n"
    "CRITICAL: You MUST output the ENTIRE Markdown document from start to finish, "
    "including all unchanged sections. Do not output just the fixes, a summary of "
    "changes, or partial sections. The output must be a complete, self-contained "
    "study guide that can be saved directly to a file."
)


# ─────────────────────────────────────────────
# 4. Helper: call the model (non-streaming)
# ─────────────────────────────────────────────
def call_model(system: str, user: str) -> str:
    """Send a non-streaming request and return the full response text."""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user}
        ],
        temperature=0.0,
        top_p=0.1,
        max_tokens=4096
    )
    return response.choices[0].message.content


# ─────────────────────────────────────────────
# 5. Pass 1 — Generate notes (streaming for UX)
# ─────────────────────────────────────────────
def generate_notes(file_content: str, filename: str) -> str:
    """Convert a raw transcript into structured Markdown study notes."""
    user_prompt = (
        f"Here is the raw transcript for the lecture '{filename}':\n\n{file_content}"
    )

    completion = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt}
        ],
        temperature=0.0,
        top_p=0.1,
        max_tokens=4096,
        stream=True
    )

    full_response = ""
    print("  Pass 1 — Generating notes:   ", end="", flush=True)
    for chunk in completion:
        if chunk.choices and chunk.choices[0].delta.content is not None:
            full_response += chunk.choices[0].delta.content
    print("[Done]")
    return full_response


# ─────────────────────────────────────────────
# 6. Pass 2 — Validate notes against transcript
# ─────────────────────────────────────────────
def validate_notes(transcript: str, notes: str) -> str:
    """Compare the generated notes against the transcript and return a gap report."""
    user_prompt = (
        f"ORIGINAL TRANSCRIPT:\n{transcript}\n\n"
        f"{'─' * 60}\n\n"
        f"GENERATED NOTES:\n{notes}"
    )

    print("  Pass 2 — Validating notes:   ", end="", flush=True)
    report = call_model(VALIDATION_PROMPT, user_prompt)
    print("[Done]")
    return report


# ─────────────────────────────────────────────
# 7. Pass 3 — Fix notes based on gap report
# ─────────────────────────────────────────────
def fix_notes(transcript: str, notes: str, report: str) -> str:
    """Apply only the fixes listed in the QA report and return the full corrected notes."""
    user_prompt = (
        f"ORIGINAL TRANSCRIPT:\n{transcript}\n\n"
        f"{'─' * 60}\n\n"
        f"CURRENT NOTES:\n{notes}\n\n"
        f"{'─' * 60}\n\n"
        f"QA REPORT — fix ONLY the issues listed below:\n{report}"
    )

    print("  Pass 3 — Fixing notes:       ", end="", flush=True)

    # max_tokens is higher here because Pass 3 must output the ENTIRE document,
    # not just the corrections. 4096 risks truncating longer study guides.
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": FIX_PROMPT},
            {"role": "user",   "content": user_prompt}
        ],
        temperature=0.0,
        top_p=0.1,
        max_tokens=8192
    )
    fixed = response.choices[0].message.content
    print("[Done]")
    return fixed


# ─────────────────────────────────────────────
# 8. Orchestrator
# ─────────────────────────────────────────────
def process_transcript(file_content: str, filename: str) -> str:
    """
    Three-pass pipeline:
      Pass 1 — Generate structured notes from the transcript.
      Pass 2 — Validate the notes against the transcript and produce a gap report.
      Pass 3 — Fix the notes using only the issues listed in the gap report.
    """
    # Pass 1: Generate
    notes = generate_notes(file_content, filename)

    # Pass 2: Validate
    report = validate_notes(file_content, notes)

    # Print the validation report so you can inspect it in the console
    print(f"\n  ── Validation Report ──\n{report}\n  {'─' * 40}")

    # Pass 3: Fix only if issues were found
    if "VALIDATION PASSED" in report:
        print("  No fixes required. Using Pass 1 output.\n")
        return notes

    fixed_notes = fix_notes(file_content, notes, report)
    return fixed_notes


# ─────────────────────────────────────────────
# 9. Main
# ─────────────────────────────────────────────
def main():
    # Create output directory if it doesn't exist
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    txt_files = [f for f in os.listdir(INPUT_DIR) if f.endswith(".txt")]

    if not txt_files:
        print("No .txt files found in the input directory.")
        return

    print(f"Found {len(txt_files)} transcript(s) to process.\n{'═' * 50}")

    for filename in txt_files:
        print(f"\nProcessing: {filename}")
        print(f"{'─' * 50}")

        file_path = os.path.join(INPUT_DIR, filename)
        with open(file_path, "r", encoding="utf-8") as f:
            raw_text = f.read()

        try:
            final_notes = process_transcript(raw_text, filename)

            output_filename = filename.replace(".txt", ".md")
            output_path = os.path.join(OUTPUT_DIR, output_filename)

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(final_notes)

            print(f"  Saved: {output_path}")

        except Exception as e:
            print(f"  ERROR processing {filename}: {e}")

    print(f"\n{'═' * 50}\nAll transcripts processed.")


if __name__ == "__main__":
    main()
