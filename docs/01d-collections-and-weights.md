---
title: Collections and weights
audience: user
type: user-guide
topic: [matsya]
---

# Collections and weights

> [!summary]
> Matsya's **retrieval index** is the store of **passages**, short pieces of the indexed files with their locations, from which a search returns those that best match a query. The index divides its files into five **collections**: this project's documentation and declarations, a private literature, journal articles, HARK and Buffer Stock Theory. This page says what each collection holds and which collections a Matsya token reads; how the options of a search, the collections, the number of passages, the named sources and the boosts, select and rank the passages; what a returned passage holds; and what Matsya itself reads when a job writes a declaration or a turn answers a question.

> [!info]- Relationship with other documents
> **Builds on** — [Reaching the service by HTTP](01c-the-service-by-http.md) §4, which sends a search and reads a passage again; the command `matsya search` of [Working with Matsya from the command line](01-working-from-the-command-line.md) §8.
> **See also** — the wiki page [Matsya collection](../../wiki/matsya_collection.md), with the number of sources in each collection.
> **Explained for developers in** — [The retrieval index](../dev-guide/01-the-retrieval-index.md), how the index is built and how a search runs.

## 1 The five collections

A **source** is one file admitted to the index, named by its source identifier, and a **collection** is a named group of sources. The index and the service's answers record a source's collection under the name `corpus`.

| Collection | What it holds |
|---|---|
| `repository` | This project's published documentation, among it the [language guide](../../Bellman-Sym/index.md), the [Bellman calculus](../../bellman-calculus/index.md) and the [concept wiki](../../wiki/index.md), with the stage files of the applications and the notebooks of the tutorials; and a private part, development notes and presentations on the theory of the language |
| `literature` | A private literature: extracts and notes of books and papers on dynamic programming, category theory and computation |
| `articles` | Journal articles, at present all from Econometrica, gathered for the [training](../dev-guide/index.md) of Matsya, the runs of a revised configuration on a set of papers: a few as the PDF files themselves, and a larger set as page-marked transcriptions and secondary readings |
| `hark` | The source code, documentation and examples of HARK, Econ-ARK's Heterogeneous Agents Resources and toolKit, at one fixed commit |
| `buffer_stock` | The LaTeX source and the PDF of the paper Theoretical Foundations of Buffer Stock Saving, at one fixed commit |

The passages a search can return depend on the version of the index the service reads. Every answer of a search names that version by `index_digest`, its **digest**, a 64-character code computed from the index's contents, which changes whenever the index is rebuilt; `matsya index` prints it.

## 2 Who reads each collection

The published part of `repository`, and `hark` and `buffer_stock`, are open to every Matsya token. The private part of `repository`, `literature` and `articles` are each read under a **grant**, a permission that the service's administrator records in the service's grant file for the holder of a Matsya token, under the names `repository-private`, `literature` and `articles`. A holder whom the grant file names holds exactly the grants named there, and every other holder receives the file's default list of grants. On the service the administrator runs, that default holds all three grants, so that every Matsya token reads all five collections unless the administrator has named its holder with fewer. A missing or malformed grant file leaves every Matsya token the published parts alone. The service reads the grant file again for every search, job and turn, so a changed grant applies from the next request.

Naming a collection in a request does not grant it. A search or an answer that names `literature` or `articles` without the grant is refused with the status 403 and the sentence `Collection access is not granted`, and nothing is searched. A search of `repository` is never refused: it returns passages of the published part, and of the private part only under its grant. A passage is returned, by a search or by `GET /v1/passages/{passage_id}`, only when the Matsya token may read its collection and part.

## 3 The options of a search

`POST /v1/search` and `POST /v1/answer` take the same JSON object, of at most 16 KiB. A field outside this table, or a value outside its range, is refused with the status 422.

| Field | What it sets | Default | Allowed values |
|---|---|---|---|
| `query` | the search text | required | a text of at most 1,000 characters that is not blank |
| `collections` | the collections searched | `["repository", "buffer_stock"]` | a non-empty list of the five names of §1 |
| `limit` | the most passages returned | 8 | an integer from 1 to 20 |
| `source_ids` | the sources the search is restricted to | every source of the collections searched | from 1 to 20 source identifiers, each a text of at most 240 characters that is not blank |
| `boosts` | a factor that multiplies the weight of a collection searched (§4) | no factor | an object whose names are among `collections`, each with a number from 0 to 1000 |

A source identifier is copied from the `source_id` of a passage that an earlier search returned. A restriction to named sources keeps the collections named and the grants: an identifier of a source outside them returns nothing. `limit` is an upper bound, and a search returns fewer passages when fewer match. `matsya search` sets `query`, `collections` with its option `--collections` and `limit` with `--limit`; the function `search` of the Python module sets all five fields.

This request searches the repository and HARK, asks for six passages and halves HARK's weight:

```json
{
  "query": "endogenous grid method with a borrowing constraint",
  "collections": ["repository", "hark"],
  "limit": 6,
  "boosts": {"hark": 0.5}
}
```

## 4 How a search ranks passages

A search first gathers candidates from each collection it reads: the 200 passages closest to the query in meaning, the 200 that best match the query's words and, when the query holds mathematical symbols, the 200 that hold the most of them. Each candidate receives the score

$$
\text{raw score} = 0.7\,\text{lexical} + 0.3\,\max(0, \text{dense}) + 0.3\,[\text{phrase}].
$$

Here *lexical* is the larger of two numbers: the score $1/(1+r)$ of the **full-text search**, the search for the query's words in the passages' headings and texts, for the passage's rank $r$, counted from 0, among the passages of its collection that best match those words, with common words such as "the", "of" and "model" left out; and the share of the query's mathematical symbols that the passage holds. *Dense* is the **cosine similarity** between the **embeddings** of the query and of the passage: the embeddings are the vectors of numbers that the embedding model assigns to texts so that texts of similar meaning receive similar vectors, and the cosine similarity of two vectors is the cosine of the angle between them, 1 when they point in the same direction and smaller the more their directions differ, down to −1. The last term, *phrase*, is 1 when the whole query, ignoring case, occurs in the passage's heading or text, and 0 otherwise. The raw score is multiplied by the collection's **weight**, and the search returns the passages with the highest weighted scores, up to `limit`, a tie going to the passage with the higher lexical score.

Every collection has the weight 1, except `buffer_stock`, whose weight is 0.01 in a search that reads more than one collection and names no `source_ids`; in such a search the passages of that one paper rank below those of the other collections unless the request raises its weight. A search of one collection, or a search restricted to named sources, gives every collection the weight 1. A factor in `boosts` multiplies this default. In a search of the repository and Buffer Stock Theory, which is the search a request without `collections` makes, `"boosts": {"buffer_stock": 100}` restores Buffer Stock Theory's weight to 1. In a search of `buffer_stock` alone its weight is already 1, and the same factor makes it 100, which changes no ranking, since every passage of that search is multiplied by the same weight.

A weight changes the order of the passages and nothing else: it makes no passage more reliable and changes no permission. A factor of 0 gives the passages of a collection the score 0 without removing them from the candidates; to leave a collection out, omit it from `collections`. The scores rank passages for one query; they are not probabilities that a passage answers the question.

## 5 What a passage holds

Each passage that a search returns, and the passage that `GET /v1/passages/{passage_id}` returns, holds these fields:

- `passage_id`, its identifier, a 64-character code computed from its file, its location and its text;
- `source_id`, the identifier of its source, which `source_ids` accepts; `corpus`, its collection; and `access`, the part of the collection it belongs to, `public`, `private` or `article`;
- `path`, the file's path within its collection's folder, and `title`, the source's title where the list of indexed sources gives one, else `null`;
- `kind`, the form of the file, `markdown`, `text`, `pdf` or `notebook`, and `authority`, the kind of source, such as `canonical` for a published page of this project, `primary` for an article or a paper itself and `secondary` for a reading of one;
- `version`, the fixed commit of HARK or of Buffer Stock Theory; for the article PDFs, and for the transcriptions and secondary readings of some of the same articles, the label of the selected set of articles; and `null` for every other source;
- `location`, where the passage stands in its file: its `heading`; its first and last lines, `line_start` and `line_end`; its first and last characters, `char_start` and `char_end`; in a PDF, `page`, the page's position in the file counted from 1, which can differ from the page number printed on it (`page_basis` is then `pdf_ordinal`); in a transcription with page markers, the `page` that the markers give, with `page_basis` `markdown_marker` and the `printed_page_label`; in a notebook, `cell_number` and `cell_type`; in a stage file, `stage_name` and `block_id`; and in a page whose headings the index records, `section`, the identifier of the innermost section;
- `text`, the passage itself;
- `index_digest`, the version of the index read; `manifest_digest` and `corpus_revision`, the versions of the list of sources and of the collection's files from which the index was built; and `file_sha256` and `passage_sha256`, the digests of the file and of the passage's text;
- `source_cluster`, the group of sources of §6 to which the source belongs, or `null`; `source_root`, the folder the file was read from; and `model_prompt`, a mark of the list of indexed sources that restricts no search.

A search adds five numbers to each passage:

| Field | What it is |
|---|---|
| `raw_score` | the score before the collection's weight (§4) |
| `retrieval_weight` | the collection's default weight multiplied by its factor in `boosts` |
| `score` | `raw_score` multiplied by `retrieval_weight`, by which the passages are ordered |
| `lexical_score` | the lexical part of the score, from the query's words or its mathematical symbols |
| `dense_score` | the cosine similarity between the embeddings of the query and of the passage |

To cite a passage, keep its `passage_id` with the `index_digest` of the answer that returned it. `GET /v1/passages/{passage_id}?index_digest=…` returns the passage again while the service keeps that version of the index and your Matsya token may read its collection ([Reaching the service by HTTP](01c-the-service-by-http.md) §4). Check a mathematical claim against the cited source before relying on it, above all in a passage of a PDF, whose extracted text can lose mathematics.

## 6 What Matsya reads when a job writes or a turn answers

The options of §3 belong to the two search routes alone. When a job writes or a turn answers, the program makes its own searches. None of them passes `boosts`, and each reads several collections, so the default weights of §4 apply: 0.01 for Buffer Stock Theory and 1 for every other collection.

In a job, the Model-prose-writer and Prose-to-Bellman-Sym, the roles described in [The roles of Matsya and when to use them](01b-the-roles-and-when-to-use-them.md) §1, receive the passages of an initial search whose query names the concepts the source material names, at most four passages at present, and each may request further searches and passages within allowances that the configuration sets; the reconstruction, in which Prose-to-Bellman-Sym writes again from the round-trip prose, makes a search of its own from that prose. These searches read the collections that the job's owner may read: the published parts for every Matsya token, and each private collection under its grant. They also leave out every source that carries a **source cluster**, the label with which the list of indexed sources groups the sources of one paper or one package, so that a job about a paper does not retrieve that paper's own text. When the job's request names `model_key` and `source_cluster` ([Reaching the service by HTTP](01c-the-service-by-http.md) §5), the job leaves out the sources of those clusters alone; when it names neither, which is the case of every job that matsya-client or matsya-master starts, the job leaves out every source that carries a cluster. At present every source of HARK, of Buffer Stock Theory and of the articles carries a cluster, and no source of the repository or of the literature does, so that a job whose request names no cluster reads the repository and, under its grant, the literature. The full view of a job's record names, under `reading`, the passages each message of a role held.

In a turn, the conversation role of matsya-master reads in the same way, through an initial search whose query is the question and through requests of its own, from every collection that the person asking may read, and it leaves out no source, since a turn writes no declaration. The passages of the literature and of the articles therefore reach the conversation role for a Matsya token granted them, as they reach the answers of `POST /v1/search` and `POST /v1/answer`.
