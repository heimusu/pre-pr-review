# pre-pr-review

> PR作成前に、独立した4つの視点でレビューさせる Claude Code の subagent + skill セット

1人（1モデル）でレビューすると、直前に自分で書いたコードは「書いたときの正しさの記憶」に引っ張られて見落としが残る。pre-pr-review は、要求・既存コードとの整合性・不具合・テストの4つの観点を**互いの指摘を見せずに独立したsubagentへ振り**、後から結果だけを統合する。1つのモデルが全部見るより、視点の汚染が起きにくい。

## 何ができるか

`/pre-pr-review` を実行すると、現在のブランチとbaseブランチの差分（未コミット変更があればそれも含む）に対して、以下の4つのsubagentを**並列・独立**に起動する。

| subagent | 観点 |
|---|---|
| `requirements-reviewer` | Issueや受け入れ条件と照合し、要求の実装漏れがないか |
| `codebase-consistency-reviewer` | 類似の既存実装と比較し、実害のある逸脱がないか |
| `bug-hunter` | null・境界値・競合・古いstateなど、実装そのものの不具合 |
| `test-reviewer` | 変更された挙動に対してテストが不足していないか |

各agentは他のagentの指摘を事前に見ない。全結果が揃ってから重複を統合し、現行コード・要件・既存テストで裏付けを取り、根拠のない指摘は捨てる。残った指摘は `Blocking` / `Should fix` / `Non-blocking` に分類され、該当箇所・条件・影響・根拠・発見したagent名とともに提示される。明示的な依頼がない限りコードは変更しない。

## インストール

Claude Code の実ディレクトリ構成（`~/.claude/agents/<namespace>/`、`~/.claude/skills/<name>/`）に合わせて、agentsとskillを別々にsymlinkする。

### 方法A: clone + symlink（推奨）

更新に追随できる。

```sh
ghq get github.com/heimusu/pre-pr-review
# または: git clone https://github.com/heimusu/pre-pr-review.git ~/src/pre-pr-review

mkdir -p ~/.claude/agents ~/.claude/skills
ln -s "$(ghq root)/github.com/heimusu/pre-pr-review/agents/review" ~/.claude/agents/review
ln -s "$(ghq root)/github.com/heimusu/pre-pr-review/skills/pre-pr-review" ~/.claude/skills/pre-pr-review
```

更新するとき:

```sh
git -C "$(ghq root)/github.com/heimusu/pre-pr-review" pull
```

### 方法B: 直接コピー

お試し用。更新は手動で入れ直す。

```sh
git clone https://github.com/heimusu/pre-pr-review.git /tmp/pre-pr-review
mkdir -p ~/.claude/agents ~/.claude/skills
cp -R /tmp/pre-pr-review/agents/review ~/.claude/agents/review
cp -R /tmp/pre-pr-review/skills/pre-pr-review ~/.claude/skills/pre-pr-review
```

プロジェクト単位で使う場合は `~/.claude/` の代わりにリポジトリ直下の `.claude/agents/`・`.claude/skills/` にリンクする。

### 動作確認

Claude Code を起動し、`/` を入力して `pre-pr-review` が候補に出れば認識されている。出ない場合は `~/.claude/skills/pre-pr-review/SKILL.md` が存在するか確認する。4つのsubagentは `/agents` コマンドの一覧、または `~/.claude/agents/review/*.md` の存在で確認できる。

## 使い方

```
/pre-pr-review
```

baseブランチやIssueへの参照を渡すと優先される。

```
/pre-pr-review main...HEAD
/pre-pr-review #123
```

未指定の場合、追跡先・PR設定・デフォルトブランチの順に調べてbaseを特定する。曖昧な場合は候補を明示して確認される。

可能であれば、実装したセッションとは別の新しいClaude Codeセッションから実行することを推奨する。実装者（自分）の説明を事実と仮定せず、差分・現行コード・要件・テスト・文書を一次情報として扱うため。

## 前提と制約

**git リポジトリ内で実行すること。** 差分が入力なので、リポジトリ外では動かない。

**要件の所在が見つからなければ、その旨が明記される。** Issueや受け入れ条件を捏造して埋めることはしない。

**コードは変更しない。** 明示的な依頼がない限り、レビュー結果を提示するだけで実装には手を入れない。

## review-history（任意の拡張）

3つのsubagent（`codebase-consistency-reviewer` / `bug-hunter` / `test-reviewer`）は、frontmatterで `review-history` という skill を参照している。これは**プロジェクトごとに任意で追加する拡張**で、このリポジトリには含まれていない。

存在すれば「そのプロジェクトで過去のPRレビューにおいて繰り返された見落としパターン」を探索の仮説として使う（指摘の証拠としては使わない）。存在しなくても4つのagentは通常どおり動作する。

自分のプロジェクト用に作る場合は、`docs/templates/review-history/` にあるテンプレートをコピーし、プレースホルダーを実際の過去レビュー傾向で埋めて、対象プロジェクトの `.claude/skills/review-history/` に配置する。

```sh
cp -R docs/templates/review-history /path/to/your-project/.claude/skills/review-history
```

**このファイルには過去の実PR番号やレビュー内容が入るため、プロジェクト固有の非公開情報として扱い、公開リポジトリにはコミットしないこと。**

## リポジトリ構成

```
agents/
  review/
    requirements-reviewer.md          要求充足レビュアー
    codebase-consistency-reviewer.md  既存コードとの整合性レビュアー
    bug-hunter.md                     不具合レビュアー
    test-reviewer.md                  テスト不足レビュアー
skills/
  pre-pr-review/
    SKILL.md                          4subagentの起動・統合・分類ルール
docs/
  templates/
    review-history/                   プロジェクトごとに作る任意拡張のテンプレート
```

## ライセンス

MIT
