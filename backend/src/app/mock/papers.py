"""Mock paper catalog and offline keyword search.

A single source of demo data shared by:

* the pipeline's multi-source recall stage,
* the agent's ``search_stub`` tool,
* the ``/papers`` database (via :mod:`app.db.seed`).

The metadata describes well-known AI/ML papers (titles/authors/venues are
real; the records are bundled here as fixture data). Search is a small,
deterministic keyword/topic scorer with a popularity fallback, so *any*
query — even one with no keyword overlap — returns a sensible ranked list
and the demo never shows an empty screen.

This module deliberately has no third-party dependencies and no I/O.
"""
from __future__ import annotations

import math
import re
from collections.abc import Iterable
from copy import deepcopy
from typing import Any

# Columns that map onto the `papers` SQL table.
DB_COLUMNS = (
    "id",
    "title",
    "abstract",
    "authors",
    "doi",
    "venue",
    "year",
    "url",
    "pdf_url",
)


def _arxiv(abs_id: str) -> tuple[str, str]:
    """Build (abstract, pdf) URL pair for an arXiv id."""
    return (
        f"https://arxiv.org/abs/{abs_id}",
        f"https://arxiv.org/pdf/{abs_id}",
    )


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

def _p(
    pid: str,
    title: str,
    authors: str,
    year: int,
    venue: str,
    topics: list[str],
    abstract: str,
    citation_count: int,
    *,
    url: str | None = None,
    pdf_url: str | None = None,
    doi: str | None = None,
    arxiv: str | None = None,
) -> dict[str, Any]:
    """Build one catalog record."""
    if arxiv is not None:
        url, pdf_url = _arxiv(arxiv)
    return {
        "id": f"paper_demo_{pid}",
        "title": title,
        "authors": authors,
        "year": year,
        "venue": venue,
        "doi": doi,
        "url": url,
        "pdf_url": pdf_url,
        "citation_count": citation_count,
        "topics": topics,
        "abstract": abstract,
    }


PAPER_CATALOG: list[dict[str, Any]] = [
    _p(
        "0001",
        "Attention Is All You Need",
        "Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, et al.",
        2017,
        "NeurIPS",
        ["transformer", "attention", "nlp", "natural language processing",
         "deep learning", "architecture", "sequence modeling", "translation"],
        "The dominant sequence transduction models rely on complex recurrent or "
        "convolutional neural networks that include an encoder and a decoder. We "
        "propose the Transformer, a simple network architecture based solely on "
        "attention mechanisms, entirely dispensing with recurrence and "
        "convolutions. Experiments on machine translation show superior quality "
        "while being more parallelizable and requiring significantly less time to "
        "train.",
        130000,
        arxiv="1706.03762",
    ),
    _p(
        "0002",
        "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
        "Jacob Devlin, Ming-Wei Chang, Kenton Lee, Kristina Toutanova",
        2019,
        "NAACL",
        ["bert", "transformer", "pretraining", "nlp", "natural language processing",
         "language model", "deep learning", "representation"],
        "We introduce a new language representation model, BERT, designed to "
        "pre-train deep bidirectional representations from unlabeled text by jointly "
        "conditioning on both left and right context in all layers. The pre-trained "
        "model can be fine-tuned with just one additional output layer to create "
        "state-of-the-art models for a wide range of natural language processing "
        "tasks.",
        125000,
        arxiv="1810.04805",
        doi="10.18653/v1/N19-1423",
    ),
    _p(
        "0003",
        "Language Models are Few-Shot Learners",
        "Tom Brown, Benjamin Mann, Nick Ryder, Melanie Subbiah, et al.",
        2020,
        "NeurIPS",
        ["gpt", "large language model", "llm", "language model", "nlp",
         "natural language processing", "few-shot", "pretraining", "transformer"],
        "Recent work has demonstrated substantial gains on many NLP tasks and "
        "benchmarks by pre-training on a large corpus of text followed by "
        "fine-tuning. We train GPT-3, an autoregressive language model with 175 "
        "billion parameters, and show that scaling up language models greatly "
        "improves task-agnostic, few-shot performance, sometimes even reaching "
        "competitiveness with prior fine-tuned approaches.",
        25000,
        arxiv="2005.14165",
    ),
    _p(
        "0004",
        "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
        "Patrick Lewis, Ethan Perez, Aleksandra Piktus, Fabio Petroni, et al.",
        2020,
        "NeurIPS",
        ["rag", "retrieval augmented generation", "retrieval", "generation",
         "nlp", "natural language processing", "knowledge", "open domain",
         "question answering"],
        "We introduce retrieval-augmented generation (RAG), where models combine a "
        "pre-trained parametric sequence-to-sequence model with a non-parametric "
        "memory accessed via a nearest-neighbor lookup over a dense index of "
        "documents. RAG combines the benefits of pre-training and retrieval and can "
        "be fine-tuned jointly, achieving strong results on knowledge-intensive NLP "
        "tasks such as open-domain question answering.",
        9000,
        arxiv="2005.11401",
    ),
    _p(
        "0005",
        "LoRA: Low-Rank Adaptation of Large Language Models",
        "Edward J. Hu, Yelong Shen, Phillip Wallis, Zeyuan Allen-Zhu, et al.",
        2022,
        "ICLR",
        ["lora", "fine-tuning", "large language model", "llm", "efficient",
         "parameter efficient", "adaptation", "language model"],
        "An important paradigm for natural language processing involves "
        "pre-training on large-scale data and fine-tuning on a task-specific "
        "dataset. We propose Low-Rank Adaptation (LoRA), which freezes the "
        "pre-trained model weights and injects trainable low-rank decomposition "
        "matrices into each layer of the Transformer architecture, greatly "
        "reducing the number of trainable parameters and GPU memory.",
        7000,
        arxiv="2106.09685",
    ),
    _p(
        "0006",
        "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models",
        "Jason Wei, Xuezhi Wang, Dale Schuurmans, Maarten Bosma, et al.",
        2022,
        "NeurIPS",
        ["chain of thought", "reasoning", "prompting", "large language model",
         "llm", "language model", "inference"],
        "We explore how generating a chain of thought — a series of intermediate "
        "reasoning steps — significantly improves the ability of large language "
        "models to perform complex reasoning. Experiments show that such reasoning "
        "abilities emerge naturally in sufficiently large language models via a "
        "simple method called chain-of-thought prompting.",
        5000,
        arxiv="2201.11903",
    ),
    _p(
        "0007",
        "Direct Preference Optimization: Your Language Model is Secretly a Reward Model",
        "Rafael Rafailov, Archit Sharma, Eric Mitchell, Christopher D. Manning, et al.",
        2023,
        "NeurIPS",
        ["dpo", "preference optimization", "alignment", "rlhf",
         "large language model", "llm", "reinforcement learning", "language model"],
        "While large-scale unsupervised language models learn broad capabilities, "
        "controlling these models remains difficult. We introduce Direct Preference "
        "Optimization (DPO), which directly optimizes a language model to align with "
        "human preferences. DPO is stable, performant, and lightweight, eliminating "
        "the need for a separate reward model or reinforcement learning fine-tuning.",
        2500,
        arxiv="2305.18290",
    ),
    _p(
        "0008",
        "Sequence to Sequence Learning with Neural Networks",
        "Ilya Sutskever, Oriol Vinyals, Quoc V. Le",
        2014,
        "NeurIPS",
        ["seq2seq", "sequence to sequence", "nlp", "natural language processing",
         "recurrent", "lstm", "deep learning", "translation", "encoder decoder"],
        "Deep Neural Networks (DNNs) are extremely powerful machine learning models "
        "that usually work well whenever large labeled training sets are available. "
        "We present a general end-to-end approach to sequence learning based on "
        "multilayered Long Short Term Memory (LSTM) networks, and show its "
        "effectiveness on the WMT-14 English-to-French translation task.",
        22000,
        arxiv="1409.3215",
    ),
    _p(
        "0009",
        "Efficient Estimation of Word Representations in Vector Space",
        "Tomas Mikolov, Kai Chen, Greg Corrado, Jeffrey Dean",
        2013,
        "ICLR Workshop",
        ["word2vec", "embedding", "word representations", "nlp",
         "natural language processing", "distributed representation"],
        "We propose two novel model architectures for computing continuous vector "
        "representations of words from very large data sets. The quality of these "
        "representations is measured in a word similarity task, and the resulting "
        "word vectors are shown to capture syntactic and semantic regularities in "
        "language.",
        28000,
        arxiv="1301.3781",
    ),
    _p(
        "0010",
        "Deep Residual Learning for Image Recognition",
        "Kaiming He, Xiangyu Zhang, Shaoqing Ren, Jian Sun",
        2016,
        "CVPR",
        ["resnet", "residual learning", "cnn", "computer vision", "image",
         "deep learning", "architecture", "visual recognition"],
        "Deeper neural networks are more difficult to train. We present a residual "
        "learning framework to ease the training of networks that are substantially "
        "deeper than those previously used. We explicitly reformulate the layers as "
        "learning residual functions with reference to the layer inputs, achieving "
        "152 layers and winning 1st place on the ILSVRC 2015 classification task.",
        210000,
        arxiv="1512.03385",
        doi="10.1109/CVPR.2016.90",
    ),
    _p(
        "0011",
        "ImageNet Classification with Deep Convolutional Neural Networks",
        "Alex Krizhevsky, Ilya Sutskever, Geoffrey E. Hinton",
        2012,
        "NeurIPS",
        ["alexnet", "cnn", "convolutional", "computer vision", "image",
         "imagenet", "deep learning", "classification"],
        "We trained a large, deep convolutional neural network to classify the 1.2 "
        "million high-resolution images in the ImageNet LSVRC-2010 contest into the "
        "1000 different classes. The network, later known as AlexNet, achieved "
        "top-5 test error rates substantially better than previous approaches and "
        "helped catalyze the deep learning era in computer vision.",
        130000,
        url="https://proceedings.neurips.cc/paper/2012/hash/c399862d3b9d6b76c8436e924a68c45b-Abstract.html",
    ),
    _p(
        "0012",
        "Very Deep Convolutional Networks for Large-Scale Image Recognition",
        "Karen Simonyan, Andrew Zisserman",
        2015,
        "ICLR",
        ["vgg", "cnn", "convolutional", "computer vision", "image",
         "deep learning", "architecture"],
        "In this work we investigate the effect of the convolutional network depth "
        "on its accuracy in a large-scale image recognition setting. Our main "
        "contribution is a thorough evaluation of networks of increasing depth using "
        "an architecture with very small convolution filters, the VGG network, which "
        "achieves significant improvements on ImageNet.",
        120000,
        arxiv="1409.1556",
    ),
    _p(
        "0013",
        "Batch Normalization: Accelerating Deep Network Training by Reducing Internal Covariate Shift",
        "Sergey Ioffe, Christian Szegedy",
        2015,
        "ICML",
        ["batch normalization", "optimization", "deep learning", "training",
         "regularization", "neural network"],
        "Training deep neural networks is complicated by the fact that the "
        "distribution of each layer's inputs changes during training. We propose "
        "Batch Normalization, a technique that normalizes layer inputs, allowing the "
        "use of higher learning rates and being less careful about initialization, "
        "while also acting as a regularizer.",
        45000,
        arxiv="1502.03167",
    ),
    _p(
        "0014",
        "Adam: A Method for Stochastic Optimization",
        "Diederik P. Kingma, Jimmy Ba",
        2015,
        "ICLR",
        ["adam", "optimizer", "optimization", "stochastic gradient descent",
         "deep learning", "training"],
        "We introduce Adam, an algorithm for first-order gradient-based optimization "
        "of stochastic objective functions, based on adaptive estimates of "
        "lower-order moments. The method is straightforward to implement, is "
        "computationally efficient, has little memory requirements, and is well "
        "suited for problems that are large in terms of data and parameters.",
        230000,
        arxiv="1412.6980",
    ),
    _p(
        "0015",
        "Dropout: A Simple Way to Prevent Neural Networks from Overfitting",
        "Nitish Srivastava, Geoffrey Hinton, Alex Krizhevsky, Ilya Sutskever, Ruslan Salakhutdinov",
        2014,
        "JMLR",
        ["dropout", "regularization", "overfitting", "deep learning",
         "neural network", "training"],
        "Deep neural nets with a large number of parameters are powerful machine "
        "learning systems, but overfitting is a serious problem in such networks. We "
        "propose dropout, a technique where randomly selected neurons are ignored "
        "during training, which provides a way of approximately combining many "
        "different neural network architectures efficiently.",
        55000,
        url="https://www.jmlr.org/papers/v15/srivastava14a.html",
    ),
    _p(
        "0016",
        "Human-level Control through Deep Reinforcement Learning",
        "Volodymyr Mnih, Koray Kavukcuoglu, David Silver, et al.",
        2015,
        "Nature",
        ["dqn", "deep reinforcement learning", "reinforcement learning", "rl",
         "q-learning", "atari", "robotics", "control", "deep learning"],
        "The theory of reinforcement learning provides a normative account rooted in "
        "psychological and neuroscientific perspectives of how agents can optimize "
        "their control. We develop a deep Q-network agent that can learn successful "
        "policies directly from high-dimensional sensory input using reinforcement "
        "learning, achieving human-level performance across many Atari 2600 games.",
        26000,
        arxiv="1312.5602",
        doi="10.1038/nature14236",
    ),
    _p(
        "0017",
        "Proximal Policy Optimization Algorithms",
        "John Schulman, Filip Wolski, Prafulla Dhariwal, Alec Radford, Oleg Klimov",
        2017,
        "arXiv",
        ["ppo", "policy gradient", "reinforcement learning", "rl",
         "robotics", "control", "optimization", "deep learning"],
        "We propose a new family of policy gradient methods for reinforcement "
        "learning which alternate between sampling data through interaction with the "
        "environment and optimizing a surrogate objective function using stochastic "
        "gradient ascent. Proximal Policy Optimization (PPO) attains the strong "
        "performance of trust-region methods while being far simpler to implement "
        "and more general, and it is widely used for robotics and control policies.",
        15000,
        arxiv="1707.06347",
    ),
    _p(
        "0018",
        "Asynchronous Methods for Deep Reinforcement Learning",
        "Volodymyr Mnih, Adria Puigdomenech Badia, Mehdi Mirza, et al.",
        2016,
        "ICML",
        ["a3c", "actor critic", "reinforcement learning", "rl",
         "asynchronous", "robotics", "control", "deep learning"],
        "We propose a conceptually simple and lightweight framework for deep "
        "reinforcement learning that uses asynchronous gradient descent for "
        "optimization of deep neural network controllers. The asynchronous "
        "advantage actor-critic (A3C) model uses a parallelized actor-learner and "
        "performs well across a variety of domains with both discrete and continuous "
        "actions.",
        9000,
        arxiv="1602.01783",
    ),
    _p(
        "0019",
        "Semi-Supervised Classification with Graph Convolutional Networks",
        "Thomas N. Kipf, Max Welling",
        2017,
        "ICLR",
        ["gcn", "graph neural network", "gnn", "graph convolution",
         "semi-supervised", "node classification", "graph", "representation"],
        "We present a scalable approach for semi-supervised learning on graph-"
        "structured data that is based on an efficient variant of convolutional "
        "neural networks which operate directly on graphs. The graph convolutional "
        "network (GCN) scales linearly in the number of graph edges and encodes both "
        "local graph structure and node features for classification.",
        22000,
        arxiv="1609.02907",
    ),
    _p(
        "0020",
        "Graph Attention Networks",
        "Petar Veličković, Guillem Cucurull, Arantxa Casanova, et al.",
        2018,
        "ICLR",
        ["gat", "graph attention network", "graph neural network", "gnn",
         "attention", "graph", "node classification", "representation"],
        "We present graph attention networks (GATs), novel neural network "
        "architectures that operate on graph-structured data and leverage masked "
        "self-attentional layers to address the shortcomings of prior methods based "
        "on graph convolutions. The attention mechanism allows attending over "
        "neighborhoods, enabling the model to assign different importance to "
        "different nodes.",
        13000,
        arxiv="1710.10903",
    ),
    _p(
        "0021",
        "Inductive Representation Learning on Large Graphs",
        "William L. Hamilton, Rex Ying, Jure Leskovec",
        2017,
        "NeurIPS",
        ["graphsage", "graph neural network", "gnn", "inductive learning",
         "embedding", "graph", "representation", "node classification"],
        "Low-dimensional embeddings of nodes in large graphs have proved extremely "
        "useful in a variety of prediction tasks. We present GraphSAGE, a general "
        "inductive framework that generates node embeddings by sampling and "
        "aggregating features from a node's local neighborhood, allowing "
        "generalization to previously unseen nodes and graphs.",
        11000,
        arxiv="1706.02216",
    ),
    _p(
        "0022",
        "Denoising Diffusion Probabilistic Models",
        "Jonathan Ho, Ajay Jain, Pieter Abbeel",
        2020,
        "NeurIPS",
        ["diffusion", "ddpm", "generative model", "image generation",
         "computer vision", "deep learning", "denoising"],
        "We present high quality image synthesis results using diffusion "
        "probabilistic models, a class of latent variable models inspired by "
        "considerations from nonequilibrium thermodynamics. Our best results on "
        "unconditional image generation on CIFAR-10 and LSUN datasets outperform "
        "previous approaches including autoregressive models and GANs.",
        11000,
        arxiv="2006.11239",
    ),
    _p(
        "0023",
        "Generative Adversarial Networks",
        "Ian J. Goodfellow, Jean Pouget-Abadie, Mehdi Mirza, et al.",
        2014,
        "NeurIPS",
        ["gan", "generative model", "adversarial", "image generation",
         "deep learning", "unsupervised"],
        "We propose a new framework for estimating generative models via an "
        "adversarial process, in which we simultaneously train two models: a "
        "generative model G that captures the data distribution and a discriminative "
        "model D that estimates the probability that a sample came from the training "
        "data rather than G.",
        42000,
        arxiv="1406.2661",
    ),
    _p(
        "0024",
        "Auto-Encoding Variational Bayes",
        "Diederik P. Kingma, Max Welling",
        2014,
        "ICLR",
        ["vae", "variational autoencoder", "generative model", "deep learning",
         "latent variable", "unsupervised", "representation"],
        "How can we perform efficient inference and learning in directed probabilistic "
        "models in the presence of continuous latent variables with intractable "
        "posterior distributions? We introduce a stochastic variational inference "
        "and learning algorithm that scales to large datasets and, under some mild "
        "differentiability conditions, even works in the intractable case.",
        38000,
        arxiv="1312.6114",
    ),
    _p(
        "0025",
        "Collaborative Filtering for Implicit Feedback Datasets",
        "Yifan Hu, Yehuda Koren, Chris Volinsky",
        2008,
        "ICDM",
        ["collaborative filtering", "recommender system", "implicit feedback",
         "recommendation", "matrix factorization"],
        "A common task of recommender systems is to improve customer experience "
        "through personalized recommendations based on prior implicit feedback. We "
        "identify unique properties of implicit feedback datasets and propose a "
        "factorization approach suited for such data, treating the confidence levels "
        "for user preferences and optimizing an alternating least squares cost "
        "function efficiently.",
        9000,
        doi="10.1109/ICDM.2008.22",
    ),
    _p(
        "0026",
        "Neural Collaborative Filtering",
        "Xiangnan He, Lizi Liao, Hanwang Zhang, Liqiang Nie, Xia Hu, Tat-Seng Chua",
        2017,
        "WWW",
        ["neural collaborative filtering", "ncf", "recommender system",
         "recommendation", "deep learning", "collaborative filtering",
         "matrix factorization"],
        "In recent years, deep neural networks have yielded immense success on speech "
        "recognition and computer vision. However, the exploration of deep neural "
        "networks on recommender systems has received relatively less scrutiny. We "
        "present a neural network architecture to model users and items for "
        "recommendation, and show that neural collaborative filtering (NCF) can model "
        "non-linear user-item interactions.",
        8000,
        arxiv="1708.05031",
    ),
    _p(
        "0027",
        "BPR: Bayesian Personalized Ranking from Implicit Feedback",
        "Steffen Rendle, Christoph Freudenthaler, Zeno Gantner, Lars Schmidt-Thieme",
        2009,
        "UAI",
        ["bpr", "bayesian personalized ranking", "recommender system",
         "recommendation", "implicit feedback", "ranking", "collaborative filtering"],
        "Item recommendation is the task of predicting a personalized ranking of "
        "items for a user. We introduce a generic optimization criterion, Bayesian "
        "Personalized Ranking (BPR), derived from the maximum posterior estimator, "
        "that directly optimizes ranking quality for implicit feedback and can be "
        "applied to a variety of model classes.",
        7000,
        arxiv="1205.2618",
    ),
    _p(
        "0028",
        "Deep Learning based Recommender System: A Survey and New Perspectives",
        "Shuai Zhang, Lina Yao, Aixin Sun, Yi Tay",
        2019,
        "ACM Computing Surveys",
        ["survey", "recommender system", "recommendation", "deep learning",
         "review", "neural network", "collaborative filtering"],
        "With the volume of online content growing rapidly, recommender systems have "
        "become an effective solution to mitigate information overload. This survey "
        "reviews the most recent research efforts on deep learning based recommender "
        "systems, categorizes existing work along recommendation tasks, models, and "
        "co-occurrence signals, and identifies open challenges and future directions.",
        4000,
        arxiv="1707.07435",
    ),
    _p(
        "0029",
        "A Simple Framework for Contrastive Learning of Visual Representations",
        "Ting Chen, Simon Kornblith, Mohammad Norouzi, Geoffrey Hinton",
        2020,
        "ICML",
        ["simclr", "contrastive learning", "self-supervised", "computer vision",
         "representation", "image", "deep learning", "unsupervised"],
        "We present SimCLR, a simple framework for contrastive learning of visual "
        "representations. Our method simplifies recent algorithms for "
        "self-supervised and semi-supervised learning, showing that composition of "
        "data augmentations and a nonlinear projection head substantially improve the "
        "quality of learned representations.",
        9000,
        arxiv="2002.05709",
    ),
    _p(
        "0030",
        "Communication-Efficient Learning of Deep Networks from Decentralized Data",
        "H. Brendan McMahan, Eider Moore, Daniel Ramage, Seth Hampson, Blaise Agüera y Arcas",
        2017,
        "AISTATS",
        ["federated learning", "fedavg", "distributed", "privacy",
         "deep learning", "optimization", "communication efficient"],
        "Modern mobile devices have access to a wealth of data suitable for learning "
        "models, yet the sensitive information is often private. We introduce "
        "federated learning and the FederatedAveraging (FedAvg) algorithm, which "
        "trains a shared model while keeping training data distributed on devices, "
        "reducing communication rounds through local computation and aggregation.",
        16000,
        arxiv="1602.05629",
    ),
]


# ---------------------------------------------------------------------------
# Tokenization / scoring
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Filler / query words that carry no topic signal.
_STOPWORDS = frozenset(
    ["the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "from", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did", "will", "would", "could", "should", "may", "might", "shall", "can", "what", "which", "who", "whom", "this", "that", "these", "those", "i", "you", "he", "she", "it", "we", "they", "me", "him", "her", "us", "them", "my", "your", "his", "its", "our", "their", "about", "into", "through", "during", "before", "after", "above", "below", "between", "out", "off", "over", "under", "again", "further", "then", "once", "here", "there", "when", "where", "why", "how", "all", "each", "every", "both", "few", "more", "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very", "just", "because", "as", "until", "while", "up", "down", "tell", "told", "find", "found", "me", "my", "please", "give", "give", "me", "show", "list", "get", "want", "need", "know", "regarding", "related", "paper", "papers", "research", "study", "studies", "article", "articles", "work", "works", "recent", "latest", "new", "good", "best", "top", "using", "use", "used", "method", "methods", "approach", "approaches"]
)

# Short abbreviations that should also match their expanded terms.
# Expansion terms contribute a reduced weight (0.5) so an exact match wins.
_ALIASES: dict[str, tuple[str, ...]] = {
    "ai": ("neural", "deep", "learning", "machine", "intelligence"),
    "ml": ("machine", "learning"),
    "dl": ("deep", "learning"),
    "nlp": ("natural", "language", "text", "transformer"),
    "rl": ("reinforcement", "policy", "reward", "control"),
    "cv": ("image", "visual", "convolutional", "vision"),
    "gnn": ("graph",),
    "llm": ("large", "language", "model"),
    "qa": ("question", "answering"),
}

# Field weights: exact title/topic hits dominate, abstract hits still count.
_W_TITLE = 3.0
_W_TOPIC = 3.0
_W_ABSTRACT = 1.0


def _normalize(tok: str) -> str:
    """Light suffix normalization (cheap stemming): networks->network, etc."""
    if len(tok) > 4 and tok.endswith("ies"):
        return tok[:-3] + "y"
    if len(tok) > 3 and tok.endswith("s") and not tok.endswith(("ss", "us", "is")):
        return tok[:-1]
    return tok


def _tokenize(text: str) -> list[str]:
    """Lowercase, split into word tokens, normalize suffixes, drop stopwords."""
    return [
        _normalize(t)
        for t in _TOKEN_RE.findall(text.lower())
        if len(t) > 1 and t not in _STOPWORDS
    ]


def _field_weights(paper: dict[str, Any]) -> dict[str, float]:
    """Map each token to the strongest field weight it appears with."""
    weights: dict[str, float] = {}
    for tok in _tokenize(paper.get("abstract", "")):
        weights[tok] = max(weights.get(tok, 0.0), _W_ABSTRACT)
    for topic in paper.get("topics", []):
        for tok in _tokenize(topic):
            weights[tok] = max(weights.get(tok, 0.0), _W_TOPIC)
    for tok in _tokenize(paper.get("title", "")):
        weights[tok] = max(weights.get(tok, 0.0), _W_TITLE)
    return weights


# Pre-compute once at import time.
_PAPER_INDEX: list[tuple[dict[str, Any], dict[str, float]]] = [
    (p, _field_weights(p)) for p in PAPER_CATALOG
]
_MAX_CITATIONS = max(p["citation_count"] for p in PAPER_CATALOG)
_MIN_YEAR = min(p["year"] for p in PAPER_CATALOG)
_MAX_YEAR = max(p["year"] for p in PAPER_CATALOG)

# Document frequency over the catalog, for IDF weighting. Tokens that appear
# in nearly every paper ("learning", "network") carry little topic signal;
# rare tokens ("graph", "policy") carry much more.
_DOC_FREQ: dict[str, int] = {}
for _, weights in _PAPER_INDEX:
    for tok in weights:
        _DOC_FREQ[tok] = _DOC_FREQ.get(tok, 0) + 1
_N_PAPERS = len(PAPER_CATALOG)


def _idf(tok: str) -> float:
    """Smoothed inverse document frequency; always positive."""
    df = _DOC_FREQ.get(tok, 0)
    return math.log((_N_PAPERS + 1) / (df + 1)) + 0.2


def _query_terms(query: str) -> list[tuple[str, float]]:
    """Expand the raw query into (token, weight) pairs."""
    terms: list[tuple[str, float]] = []
    seen: set[str] = set()
    for tok in _tokenize(query):
        if tok in seen:
            continue
        seen.add(tok)
        terms.append((tok, 1.0))
        for extra in _ALIASES.get(tok, ()):
            if extra not in seen:
                seen.add(extra)
                terms.append((extra, 0.5))
    return terms


def _relevance(paper_weights: dict[str, float], terms: Iterable[tuple[str, float]]) -> float:
    """Field- and IDF-weighted token overlap (term frequency is ignored)."""
    score = 0.0
    for tok, q_weight in terms:
        field_w = paper_weights.get(tok)
        if field_w:
            score += q_weight * field_w * _idf(tok)
    return score


def search_mock_papers(
    query: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Return a ranked, query-aware list of *copies* of catalog papers.

    Papers are scored by keyword overlap with title/topics/abstract. If the
    query matches nothing (e.g. an unrelated or non-English query), a
    popularity-ranked fallback is returned so the demo is never empty.

    Args:
        query: Free-text search query.
        limit: Maximum number of results to return.

    Returns:
        New paper dicts (safe to mutate) with a ``score`` field in ``[0,1]``,
        sorted by descending relevance.
    """
    limit = max(1, min(limit, len(PAPER_CATALOG)))
    terms = _query_terms(query)

    scored: list[tuple[float, dict[str, Any]]] = []
    for paper, weights in _PAPER_INDEX:
        scored.append((_relevance(weights, terms), paper))

    matched = [(r, p) for r, p in scored if r > 0]
    fallback = not matched

    if fallback:
        # No keyword overlap: rank by a blended impact + recency score.
        year_span = max(_MAX_YEAR - _MIN_YEAR, 1)

        def _popularity(paper: dict[str, Any]) -> float:
            cit_norm = paper["citation_count"] / _MAX_CITATIONS
            year_norm = (paper["year"] - _MIN_YEAR) / year_span
            return 0.50 + 0.15 * cit_norm + 0.05 * year_norm

        ranked = sorted(
            PAPER_CATALOG,
            key=lambda p: (_popularity(p), p["citation_count"], p["year"]),
            reverse=True,
        )
        out: list[dict[str, Any]] = []
        for paper in ranked[:limit]:
            row = deepcopy(paper)
            row["score"] = round(_popularity(paper), 3)
            row["match"] = "fallback"
            out.append(row)
        return out

    # Rank matched papers: relevance first, then citations, then recency.
    matched.sort(key=lambda rp: (rp[0], rp[1]["citation_count"], rp[1]["year"]), reverse=True)
    top_rel = matched[0][0]
    results = matched[:limit]

    out = []
    for rel, paper in results:
        row = deepcopy(paper)
        # Map normalized relevance into a believable 0.60–0.99 band.
        row["score"] = round(0.60 + 0.39 * (rel / top_rel), 3)
        row["match"] = "keyword"
        out.append(row)
    return out


def demo_db_rows() -> list[dict[str, Any]]:
    """Return catalog rows projected to the `papers` SQL table columns."""
    return [{col: paper[col] for col in DB_COLUMNS} for paper in PAPER_CATALOG]
