# Listings added by hand: jobs announced somewhere no adapter reads, such as
# an office's own press release. The daily ingest syncs this list like any
# other source (source_system "manual"), so a job closes after its entry is
# removed or its closing_at passes. source_job_id must stay the same once a
# job is live, or it gets a new slug.
#
# source_organization uses the names in member_parties.py ("Rep. First Last")
# so the party, state and committee filters work, and so an HVAPS or Domewatch
# copy of the same job is recognized as a duplicate.

from datetime import datetime, timezone

MANUAL_JOBS: list[dict] = [
    {
        "source_job_id": "moran-ai-policy-fellow-2026-10",
        "source_organization": "Rep. Nathaniel Moran",
        "title": "Artificial Intelligence Policy Fellow",
        "source_url": "https://moran.house.gov/news/documentsingle.aspx?DocumentID=2949",
        "location_text": "Washington, DC",
        "posted_at": datetime(2026, 10, 20, tzinfo=timezone.utc),
        "closing_at": None,
        "description": [
            (
                "Congressman Nathaniel Moran (TX-01) is hiring an Artificial "
                "Intelligence Policy Fellow for his Washington office. The paid "
                "position will support his work on emerging technology and "
                "national security. Congressman Moran serves on the House Ways and "
                "Means Committee and the House Select Committee on the Chinese "
                "Communist Party."
            ),
            (
                "The AI Policy Fellow will: research AI capabilities and risks; "
                "track AI-related legislation and hearings; and prepare the "
                "Congressman for engagement with think tanks, industry leaders, "
                "academia, and federal agencies."
            ),
            (
                "Candidates with experience in AI, policy research, or national "
                "security are encouraged to apply. Eligibility depends on "
                "experience."
            ),
            (
                "To apply, send a one-page resume and a one-page, single-spaced "
                "cover letter as PDF attachments to Amanda.Baldwin@mail.house.gov. "
                "Additional materials may be requested."
            ),
        ],
    },
]
