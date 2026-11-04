"""Registry of interim AP result events.

To add an event: add an entry here, create `ap_results/<name>/` with a
README, and point `builder` at a module exposing `build(event, fetch)`.
A stage's builder can be reused across years by reference.
"""

from dataclasses import dataclass, field
from importlib import import_module

from . import DATA_DIR, PACKAGE_DIR


@dataclass(frozen=True)
class Event:
    name: str
    election_date: str
    stage: str
    # snapshot suffix -> extra query params; one feed request per entry
    feed_params: dict
    # AP officeName values in scope
    offices: frozenset
    # module (relative to this package) exposing build(event, fetch)
    builder: str
    # (office, district, candidate name) tuples name matching cannot catch
    incumbent_overrides: frozenset = field(default_factory=frozenset)

    @property
    def event_dir(self):
        return PACKAGE_DIR / self.name

    @property
    def snapshot_dir(self):
        return self.event_dir / "snapshots"

    @property
    def out_dir(self):
        return DATA_DIR / self.name

    def build(self, fetch=False):
        import_module(f".{self.builder}", __package__).build(self, fetch)


# Incumbents that name matching cannot catch for the 2026 cycle. Both the SEC
# listing and AP use the 2026 ballot spelling.
OVERRIDES_2026 = frozenset({
    # "Jo Comerford" (electionstats) -> "Joanne M. Comerford"
    ("State Senate", "Hampshire, Franklin and Worcester", "Joanne M. Comerford"),
    # "Brandy Fluker Oakley" (electionstats) -> "Brandy Fluker Reid"
    ("State Representative", "Twelfth Suffolk", "Brandy Fluker Reid"),
})


EVENTS = {
    e.name: e for e in [
        Event(
            name="primary_2026",
            election_date="2026-09-01",
            stage="primary",
            # The feed splits the two primaries into separate responses.
            feed_params={"dem": {"party": "dem"}, "gop": {"party": "gop"}},
            offices=frozenset({
                "U.S. Senate", "Governor", "U.S. House",
                "Governor's Council", "State Senate", "State House",
            }),
            builder="primary_2026.results",
            incumbent_overrides=OVERRIDES_2026,
        ),
    ]
}
