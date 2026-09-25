# pre-pr-review

> PR作成前に、独立した4つの観点でレビューする Claude Code / Codex 向けsubagent + skillセット

1人（1モデル）でレビューすると、直前に自分で書いたコードは「書いたときの正しさの記憶」に引っ張られて見落としが残る。pre-pr-review は、要求・既存コードとの整合性・不具合・テストの4つの観点を、互いの指摘を見せずに独立したsubagentへ振り、後から結果だけを統合する。

## 何ができるか

skillを実行すると、現在のブランチとbaseブランチの差分（未コミット変更があればそれも含む）に対して、以下の4つのsubagentを独立して起動する。実行環境に十分な枠があれば並列、足りなければ先行結果を渡さずにwave実行する。

| subagent | 観点 |
|---|---|
| `requirements-reviewer` | Issueや受け入れ条件と照合し、要求の実装漏れがないか |
| `codebase-consistency-reviewer` | 類似の既存実装と比較し、実害のある逸脱がないか |
| `bug-hunter` | null・境界値・競合・古いstateなど、実装そのものの不具合 |
| `test-reviewer` | 変更された挙動に対してテストが不足していないか |

対応するnamed custom agentがあれば使い、なければskillに同梱した役割定義をgeneric subagentへ渡す。全結果が揃ってから重複を統合し、現行コード・要件・既存テストで裏付けを取る。残った指摘は `Blocking` / `Should fix` / `Non-blocking` に分類される。明示的な依頼がない限りコードは変更しない。

## インストール

最初にリポジトリをcloneする。

```sh
ghq get github.com/heimusu/pre-pr-review
# または: git clone https://github.com/heimusu/pre-pr-review.git ~/src/pre-pr-review
```

### Claude Code

Claude Codeの実ディレクトリ構成に合わせて、agentsとskillを別々にsymlinkする。

```sh
mkdir -p ~/.claude/agents ~/.claude/skills
ln -s "$(ghq root)/github.com/heimusu/pre-pr-review/agents/review" ~/.claude/agents/review
ln -s "$(ghq root)/github.com/heimusu/pre-pr-review/skills/pre-pr-review" ~/.claude/skills/pre-pr-review
```

Claude Codeを起動し、`/` を入力して `pre-pr-review` が候補に出ればskillが認識されている。4つのnamed subagentは `/agents` で確認できる。

### Codex

skillは `~/.agents/skills`、custom agentは `~/.codex/agents` にsymlinkする。custom agentが認識されない環境でも、skillはgeneric subagentで同じ4観点を実行できる。

```sh
mkdir -p ~/.agents/skills ~/.codex/agents
ln -s "$(ghq root)/github.com/heimusu/pre-pr-review/skills/pre-pr-review" ~/.agents/skills/pre-pr-review
ln -s "$(ghq root)/github.com/heimusu/pre-pr-review/.codex/agents/"*.toml ~/.codex/agents/
```

Codexを再起動し、`/skills` または `$` の候補に `pre-pr-review` が出れば認識されている。実行中のsubagentは `/agent` で確認できる。

symlinkでインストールした場合は、以下でClaude Code / Codexの両方を更新できる。

```sh
git -C "$(ghq root)/github.com/heimusu/pre-pr-review" pull
```

4つのsubagentを同時実行したい場合は、Codexの `config.toml` で並列枠を4以上にできる。設定しない場合や実行環境の上限が低い場合はwave実行になる。

```toml
[agents]
max_concurrent_threads_per_session = 4
```

### 直接コピーする場合

symlinkの代わりに以下をコピーできる。更新時は再コピーが必要になる。

```sh
# Claude Code
mkdir -p ~/.claude/agents/review ~/.claude/skills/pre-pr-review
cp -R skills/pre-pr-review/. ~/.claude/skills/pre-pr-review/
cp -R agents/review/. ~/.claude/agents/review/

# Codex
mkdir -p ~/.agents/skills/pre-pr-review ~/.codex/agents
cp -R skills/pre-pr-review/. ~/.agents/skills/pre-pr-review/
cp .codex/agents/*.toml ~/.codex/agents/
```

プロジェクト単位で使う場合は、Claude Codeでは対象プロジェクトの `.claude/agents` と `.claude/skills`、Codexでは `.codex/agents` と `.agents/skills` に同じファイルを配置する。

## 使い方

Claude Code:

```text
/pre-pr-review
/pre-pr-review main...HEAD
/pre-pr-review #123
```

Codex:

```text
$pre-pr-review
$pre-pr-review main...HEAD
$pre-pr-review #123
```

baseやIssueが未指定な場合は、追跡先・PR設定・デフォルトブランチの順に調べる。曖昧な場合は候補を明示して確認する。

可能であれば、実装したセッションとは別の新しいセッションから実行することを推奨する。

## 前提と制約

**gitリポジトリ内で実行すること。** 差分が入力なので、リポジトリ外では動かない。

**要件の所在が見つからなければ、その旨が明記される。** Issueや受け入れ条件を捏造して埋めない。

**コードは変更しない。** 明示的な依頼がない限り、レビュー結果を提示するだけで実装には手を入れない。Codex custom agentには `read-only` sandboxを既定として指定しているが、親セッションのruntime permissionが優先される場合もファイルを変更しない。workspaceへの書き込みを要するテストが実行できない場合は、未検証理由として記録する。

## review-history（任意の拡張）

`codebase-consistency-reviewer` / `bug-hunter` / `test-reviewer` は、プロジェクト固有の `review-history` skillがあれば、過去のPRレビューで繰り返された見落としパターンを探索の仮説として使う。指摘の証拠としては使わない。存在しなくても4つのagentは通常どおり動作する。

対象プロジェクトの以下のいずれかに、`docs/templates/review-history` をコピーして使う。

```text
.claude/skills/review-history/  # Claude Code
.agents/skills/review-history/  # Codex
```

**このファイルには過去の実PR番号やレビュー内容が入るため、プロジェクト固有の非公開情報として扱い、公開リポジトリにはコミットしないこと。**

## リポジトリ構成

```text
.codex/
  agents/                                  Codex用custom agent定義
agents/
  review/                                  Claude Code用custom agent定義
skills/
  pre-pr-review/
    SKILL.md                               共通オーケストレーション
    agents/openai.yaml                     Codexの明示起動ポリシー
    references/                            generic subagent用の4役割定義
docs/
  templates/review-history/                プロジェクトごとに作る任意拡張
```

## ライセンス

MIT
