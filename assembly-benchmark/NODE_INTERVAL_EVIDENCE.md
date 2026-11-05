# Recorded origin intervals inside graph nodes

The backend accepts **existing recorded metadata**, not sequences. It does not
run an aligner, derive matches from contig names, project contig-path positions
onto nodes, or change recovery scores.

`graph_artifacts.reference_interval_evidence` is an optional version-1 document:

```json
{
  "schema_version": 1,
  "evidence_type": "graph_node_to_reference",
  "coordinate_system": "0-based half-open",
  "input_hashes": {
    "assembly_sha256": "64 lowercase hexadecimal characters",
    "truth_sha256": "64 lowercase hexadecimal characters",
    "gfa_sha256": "64 lowercase hexadecimal characters"
  },
  "source": {"name": "saved evidence source", "sha256": "64 lowercase hexadecimal characters"},
  "alignments": [{
    "id": "unique-row-id", "node_id": "node-1", "node_interval": [0, 400],
    "reference_id": "reference-A", "reference_interval": [100, 500],
    "strand": "+", "assignment_status": "supported",
    "match_quality": {"identity_fraction": 1.0, "mapping_quality": 60}
  }]
}
```

Lengths and accessions must exist in the graph/reference inventory. All three
input hashes must match the scored execution and final graph. Unknown IDs,
invalid bounds/strands, duplicate row IDs, missing assignment decisions and
nonfinite quality values fail validation. `assignment_status` must explicitly
state `supported` or `ambiguous`; quality values alone never establish uniqueness.
The source name/hash are retained as supplied provenance, not independently
verified against a newly collected alignment file by this adapter.

The adapter partitions each measured node at recorded alignment endpoints:

- A single reference with explicitly supported evidence uses its stable colour.
- Multiple reference candidates or any ambiguous support remain grey.
- Gaps without recorded support remain grey and are labelled separately.
- Original alignment spans remain intact. An overlapping display chunk does not
  acquire invented reference coordinates through interpolation.

The bundle exports `report_evidence.reference_origins.node_intervals`. The viewer
shows its portions by default. Click a portion or use the interval dropdown to
inspect candidate references, original node/reference coordinates, orientation,
recorded quality and source checksum. Tiny portions remain selectable through
the dropdown. Without these records, existing whole-segment/path evidence stays
available and is not relabelled as internal mapping.

Self-overlap evidence is a separate future data product. It cannot populate this
reference-origin document. Alignment endpoints are match boundaries, not proven
biological junctions or an explanation of an assembler's internal mechanism.

Synthetic tests cover single-origin, mixed-origin, shared-repeat and unsupported
portions, overlapping rows, stale inputs and invalid evidence. The synthetic
preview is outside the deployed website. Existing frozen results currently have
no direct node interval document; their unmeasured boundaries stay unmeasured.
