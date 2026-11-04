# RefSeq reference shortlist: E. coli and K. pneumoniae

Checked against live NCBI metadata on **4 November 2026**. This is a shortlist of strong gold-standard candidates, not certification that every sequence or plasmid complement is error-free. Five preferred candidates cover **0, 1, 2, 5 and 6 deposited plasmids**, with plasmids from **3,478 to 204,698 bp**. Two additional assemblies are held because their metadata indicates ambiguous/non-ACGT positions.

## Preferred candidates

All five are current RefSeq complete-genome assemblies. Nucleotide records identify all their deposited replicons as circular. Counts below describe the deposited assembly, not a guarantee of plasmid content in every culture of that strain.

### Escherichia coli str. K-12 substr. MG1655

RefSeq assembly: [GCF_000005845.2](https://www.ncbi.nlm.nih.gov/datasets/genome/GCF_000005845.2/); paired GenBank: `GCA_000005845.2`. **0 deposited plasmids**.

Chromosome-only negative control. This is the canonical MG1655 reference, not an arbitrary newer assembly with a similar strain name. Its sequence has a history of independent correction and comparison [1].

BioSample: [SAMN02604091](https://www.ncbi.nlm.nih.gov/biosample/SAMN02604091); BioProject: [PRJNA225](https://www.ncbi.nlm.nih.gov/bioproject/PRJNA225).

| Replicon | RefSeq accession.version | GenBank accession.version | Length (bp) |
| --- | --- | --- | ---: |
| chromosome | [NC_000913.3](https://www.ncbi.nlm.nih.gov/nuccore/NC_000913.3) | U00096.3 | 4,641,652 |

### Escherichia coli W

RefSeq assembly: [GCF_000258145.1](https://www.ncbi.nlm.nih.gov/datasets/genome/GCF_000258145.1/); paired GenBank: `GCA_000258145.1`. **2 deposited plasmids**.

Small-plus-large pair. Use this University of Florida W assembly, whose publication describes optical mapping, 454 sequencing and Illumina resequencing [2]. It is distinct from the AIBN/KRIBB assembly discussed below; do not combine their replicons.

BioSample: [SAMN02604169](https://www.ncbi.nlm.nih.gov/biosample/SAMN02604169); BioProject: [PRJNA62301](https://www.ncbi.nlm.nih.gov/bioproject/PRJNA62301).

| Replicon | RefSeq accession.version | GenBank accession.version | Length (bp) |
| --- | --- | --- | ---: |
| chromosome | [NC_017664.1](https://www.ncbi.nlm.nih.gov/nuccore/NC_017664.1) | CP002967.1 | 4,897,452 |
| pRK1 | [NC_017665.1](https://www.ncbi.nlm.nih.gov/nuccore/NC_017665.1) | CP002968.1 | 102,535 |
| pRK2 | [NC_017662.1](https://www.ncbi.nlm.nih.gov/nuccore/NC_017662.1) | CP002969.1 | 5,360 |

### Escherichia coli SE11

RefSeq assembly: [GCF_000010385.1](https://www.ncbi.nlm.nih.gov/datasets/genome/GCF_000010385.1/); paired GenBank: `GCA_000010385.1`. **6 deposited plasmids**.

Six-plasmid complement spanning three small plasmids and three larger plasmids. The primary complete-genome study reports this complement and the matching sizes [3]. W and SE11 are both phylogroup B1, so they do not provide broad species diversity.

BioSample: [SAMD00061087](https://www.ncbi.nlm.nih.gov/biosample/SAMD00061087); BioProject: [PRJNA18057](https://www.ncbi.nlm.nih.gov/bioproject/PRJNA18057).

| Replicon | RefSeq accession.version | GenBank accession.version | Length (bp) |
| --- | --- | --- | ---: |
| chromosome | [NC_011415.1](https://www.ncbi.nlm.nih.gov/nuccore/NC_011415.1) | AP009240.1 | 4,887,515 |
| pSE11-1 | [NC_011419.1](https://www.ncbi.nlm.nih.gov/nuccore/NC_011419.1) | AP009241.1 | 100,021 |
| pSE11-2 | [NC_011413.1](https://www.ncbi.nlm.nih.gov/nuccore/NC_011413.1) | AP009242.1 | 91,158 |
| pSE11-3 | [NC_011416.1](https://www.ncbi.nlm.nih.gov/nuccore/NC_011416.1) | AP009243.1 | 60,555 |
| pSE11-4 | [NC_011407.1](https://www.ncbi.nlm.nih.gov/nuccore/NC_011407.1) | AP009244.1 | 6,929 |
| pSE11-5 | [NC_011408.1](https://www.ncbi.nlm.nih.gov/nuccore/NC_011408.1) | AP009245.1 | 5,366 |
| pSE11-6 | [NC_011411.1](https://www.ncbi.nlm.nih.gov/nuccore/NC_011411.1) | AP009246.1 | 4,082 |

### Klebsiella pneumoniae subsp. pneumoniae Ecl8

RefSeq assembly: [GCF_024397815.1](https://www.ncbi.nlm.nih.gov/datasets/genome/GCF_024397815.1/); paired GenBank: `GCA_024397815.1`. **1 deposited plasmid**.

Single large-plasmid baseline. NCBI identifies this as the improved hybrid Ecl8 assembly, with PacBio Sequel and Illumina NovaSeq data and Unicycler v0.4.8. Use these accession versions rather than silently substituting the older HF536482/HF536483 records. Hybrid assembly is supporting evidence, not independent proof of performance for Unicycler-derived workflows.

BioSample: [SAMN18721477](https://www.ncbi.nlm.nih.gov/biosample/SAMN18721477); BioProject: [PRJNA721588](https://www.ncbi.nlm.nih.gov/bioproject/PRJNA721588).

| Replicon | RefSeq accession.version | GenBank accession.version | Length (bp) |
| --- | --- | --- | ---: |
| chromosome | [NZ_CP073076.1](https://www.ncbi.nlm.nih.gov/nuccore/NZ_CP073076.1) | CP073076.1 | 5,306,902 |
| pEcl8 | [NZ_CP073077.1](https://www.ncbi.nlm.nih.gov/nuccore/NZ_CP073077.1) | CP073077.1 | 204,698 |

### Klebsiella pneumoniae subsp. pneumoniae MGH 78578

RefSeq assembly: [GCF_000016305.1](https://www.ncbi.nlm.nih.gov/datasets/genome/GCF_000016305.1/); paired GenBank: `GCA_000016305.1`. **5 deposited plasmids**.

Five-plasmid complement with two small and three larger plasmids. The NCBI submission records finishing evidence including double-strand/alternative-chemistry or high-quality read support and attempts to resolve repeats [4]. Selected here for its reference provenance, sizes and molecule count.

BioSample: [SAMN02603941](https://www.ncbi.nlm.nih.gov/biosample/SAMN02603941); BioProject: [PRJNA31](https://www.ncbi.nlm.nih.gov/bioproject/PRJNA31).

| Replicon | RefSeq accession.version | GenBank accession.version | Length (bp) |
| --- | --- | --- | ---: |
| chromosome | [NC_009648.1](https://www.ncbi.nlm.nih.gov/nuccore/NC_009648.1) | CP000647.1 | 5,315,120 |
| pKPN3 | [NC_009649.1](https://www.ncbi.nlm.nih.gov/nuccore/NC_009649.1) | CP000648.1 | 175,879 |
| pKPN4 | [NC_009650.1](https://www.ncbi.nlm.nih.gov/nuccore/NC_009650.1) | CP000649.1 | 107,576 |
| pKPN5 | [NC_009651.1](https://www.ncbi.nlm.nih.gov/nuccore/NC_009651.1) | CP000650.1 | 88,582 |
| pKPN6 | [NC_009652.1](https://www.ncbi.nlm.nih.gov/nuccore/NC_009652.1) | CP000651.1 | 4,259 |
| pKPN7 | [NC_009653.1](https://www.ncbi.nlm.nih.gov/nuccore/NC_009653.1) | CP000652.1 | 3,478 |

## Held alternatives

These are useful comparison records, but should not enter the exact-read panel without resolving their ambiguity policy. The reported non-ACGT counts are calculated from NCBI assembly statistics as `total_sequence_length - atgc_count`; they are metadata findings, not a direct FASTA audit. Zero reported gap length does not establish zero ambiguous bases.

- **Escherichia coli W**, [GCF_000184185.1](https://www.ncbi.nlm.nih.gov/datasets/genome/GCF_000184185.1/): 2 plasmids; **1 metadata-indicated non-ACGT positions**. This is the original Archer et al. W assembly [5], not the preferred optical-map-associated assembly above.
  chromosome: `NC_017635.1` (4,900,968 bp); pRK1: `NC_017637.1` (102,536 bp); pRK2: `NC_017636.1` (5,360 bp).

- **Klebsiella pneumoniae KCTC 2242**, [GCF_000220485.1](https://www.ncbi.nlm.nih.gov/datasets/genome/GCF_000220485.1/): 1 plasmid; **7 metadata-indicated non-ACGT positions**. The publication describes PCR/Sanger finishing and one 202,852-bp plasmid [6], but the metadata ambiguity requires review.
  chromosome: `NC_017540.1` (5,259,571 bp); pKCTC2242: `NC_017541.1` (202,852 bp).

## Benchmark use and remaining curation

Use MG1655 as the chromosome-only control, Ecl8 for a native single-plasmid baseline, W for the small/large pair, and SE11 plus MGH 78578 for multiple-plasmid recovery. Controlled zero/one/multiple-plasmid subsets can be derived computationally from the same source assembly; label them as derived subsets, not additional natural isolates. Keep each assembly's chromosome and plasmids together when describing native complements.

This shortlist does not cover plasmids below 3,478 bp, biologically linear plasmids, or every count between zero and six. It is a starting panel rather than a representative sample of either species. The separate linear-plasmid candidates are in the [methods notes](../METHODS.md#linear-plasmids-s5).

Before admitting a candidate as benchmark truth:

1. Retrieve the exact listed assembly and all its replicons. Check the sequence inventory, gaps, ambiguous bases and topology against these metadata snapshots; calculate sequence-file and per-replicon checksums. Do not silently replace ambiguous bases or mix alternative assemblies.
2. Review supporting sequence/structural evidence, especially small-plasmid completeness and circular joins. Record uncertainties and accepted exclusions. The absence of reported non-ACGT positions is only a screening check.
3. For later real-data benchmarking, verify the read-run accessions and isolate/culture match separately. BioProject or SRA sample linkage alone does not establish an appropriate matched nanopore dataset. No matched ONT run set has been validated here.
4. Record a dated admission decision. Preserve these accession versions even if annotations or the preferred NCBI assembly change.

## Machine-readable records and provenance

- [assemblies.tsv](assemblies.tsv): seven assembly-level records, including selection status, counts, metadata quality findings, BioSample/BioProject and available sequencing provenance.
- [replicons.tsv](replicons.tsv): 24 chromosome/plasmid records across preferred and held assemblies, including accession versions, lengths, topology and source links.
- [panel.json](panel.json): the same inventory with metadata-source URLs and explicit pending sequence-audit/admission status. Sequence checksums are null because sequences have not been downloaded or audited.
- [ncbi/](ncbi/): saved NCBI Datasets assembly/sequence reports and Nucleotide summaries used to verify the inventory. [SHA256SUMS](ncbi/SHA256SUMS) hashes these metadata snapshots, not genome sequences.

Counts are calculated from each sequence report's chromosome/plasmid molecule assignments. Do not use the assembly-level field named `total_number_of_chromosomes` as a biological chromosome count: in these reports it can include plasmids. Missing technology fields are recorded as `not_reported`, not inferred from unrelated assemblies of the same strain.

Metadata endpoints used: NCBI Datasets `https://api.ncbi.nlm.nih.gov/datasets/v2/genome/accession/{assembly}/dataset_report` and `.../sequence_reports`, plus NCBI E-utilities Nucleotide `esummary` for the exact accession versions. Full per-assembly Datasets URLs are recorded in `panel.json`. No genome FASTA or sequencing-read files are included.

## Supporting sources

1. [Hayashi et al., 2006: highly accurate E. coli K-12 MG1655 and W3110 sequences](https://pubmed.ncbi.nlm.nih.gov/16738553/) and the [current pinned MG1655 assembly](https://www.ncbi.nlm.nih.gov/datasets/genome/GCF_000005845.2/). The historical paper supports the curation history, not a claim that it directly validated every later sequence version.
2. [Turner et al., 2012: optical mapping and sequencing study including parent E. coli W](https://academic.oup.com/jimb/article/39/4/629/5994587). Use the parent W accessions CP002967–CP002969, not the engineered KO11 derivatives also described in that paper.
3. [Oshima et al., 2008: complete genome and six-plasmid complement of E. coli SE11](https://pubmed.ncbi.nlm.nih.gov/18931093/) and [full primary study](https://pmc.ncbi.nlm.nih.gov/articles/PMC2608844/).
4. [MGH 78578 RefSeq chromosome record and submission finishing comments](https://www.ncbi.nlm.nih.gov/nuccore/NC_009648.1?report=genbank); the saved assembly report also retains these comments.
5. [Archer et al., 2011: original E. coli W genome study](https://pmc.ncbi.nlm.nih.gov/articles/PMC3032704/). This corresponds to held assembly GCF_000184185.1, not preferred assembly GCF_000258145.1.
6. [Shin et al., 2012: complete KCTC 2242 genome study](https://pmc.ncbi.nlm.nih.gov/articles/PMC3347200/).
7. [Ecl8 BioProject PRJNA721588](https://www.ncbi.nlm.nih.gov/bioproject/PRJNA721588) and [NCBI assembly metadata](https://api.ncbi.nlm.nih.gov/datasets/v2/genome/accession/GCF_024397815.1/dataset_report) document the improved hybrid assembly. Its supporting evidence here is submission metadata; an independent per-replicon validation has not been established.
