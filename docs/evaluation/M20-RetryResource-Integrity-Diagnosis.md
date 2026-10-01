# M20 Retry/Resource Integrity Diagnosis

The #267 Fixed v3 record is invalid evidence. Its five persisted physical
attempts have five distinct logical-operation IDs and retry index zero on each,
while resource accounting charges only four logical provider interactions.
Consequently the fifth physical attempt cannot be identified as a retry of a
parent logical operation.

The canonical validator correctly rejects this mismatch. The evidence remains
immutable and invalid; no provider execution may be reauthorized from it. A
separate prospective persistence remediation and new execution generation are
required.
