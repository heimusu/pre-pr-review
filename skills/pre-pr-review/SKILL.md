---
name: pre-pr-review
description: PR作成前に4つの独立した観点から現在のブランチの差分をレビューし、根拠のある指摘を統合する。
disable-model-invocation: true
---

# PR作成前レビュー

同じユーザーメッセージでbaseブランチやIssueへの参照が指定されていれば優先する。未指定なら追跡先、PR設定、デフォルトブランチの順に調べてbaseを特定する。曖昧なら候補を明示して確認する。マージベースから現在のHEADまでの差分に加え、未コミット変更があればその有無を明記して対象に含める。削除・改名・新規ファイルも確認する。

可能なら実装セッションとは別の新しいセッションから実行する。実装者の説明は事実と仮定せず、差分、現行コード、要件、テスト、文書を一次情報として扱う。要件の所在を探し、見つからなければその限界を示す。

## 独立レビュー

次の役割定義を読み、各役割を1つの独立したsubagentに割り当てる。

1. [requirements-reviewer](references/requirements-reviewer.md)
2. [codebase-consistency-reviewer](references/codebase-consistency-reviewer.md)
3. [bug-hunter](references/bug-hunter.md)
4. [test-reviewer](references/test-reviewer.md)

対応するnamed custom agentが利用可能なら使う。Claude Codeでは `requirements-reviewer` / `codebase-consistency-reviewer` / `bug-hunter` / `test-reviewer`、Codexでは `requirements_reviewer` / `codebase_consistency_reviewer` / `bug_hunter` / `test_reviewer` を対応させる。利用できない環境では、役割定義の全文をgeneric subagentの依頼に含める。

各subagentには同じbase、差分範囲、利用可能な要件の所在、その役割定義だけを渡す。他のsubagentの指摘や結論は事前に渡さない。独立したコンテキストを作れる場合は使う。並列実行が可能なら並列に起動し、実行枠が4未満なら利用可能な最大数ごとにwave実行する。waveを跨いでも先行する結果を後続subagentに渡さない。

subagentを起動する前に、同梱の [探索スクリプト](scripts/find_review_history.py) を必ず実行してリポジトリ固有の `review-history` を探す。スクリプトのパスは読み込んだこの `SKILL.md` のディレクトリを基準に絶対パスへ解決し、`--repo` にはレビュー対象worktree内のディレクトリを指定する。Claude Codeでは `--runtime claude`、Codexでは `--runtime codex` を使う。

```sh
python3 "<このスキルの絶対パス>/scripts/find_review_history.py" --runtime codex --repo "<レビュー対象worktreeの絶対パス>"
```

スクリプトは現在のworktreeの `.claude/skills/review-history/SKILL.md` または `.agents/skills/review-history/SKILL.md` を確認し、不在ならGitのworktree情報からmain worktreeを特定して同じパスを確認する。現在のworktreeを優先し、他のlinked worktreeや単純な親ディレクトリ探索は行わない。

JSON出力の `status` に従う。`found`（終了コード0）なら `path` の指示を読み、直接参照された事例はそのファイルのディレクトリを基準に解決して読む。参照ファイルの読み取り失敗も不在として扱わず、理由を記録する。`missing`（終了コード1）の場合だけ履歴なしとして進める。`error`（終了コード2）、Python/Gitの実行不能、スクリプト未実行は「探索失敗／未検証」として理由を記録し、履歴なしと断定しない。Review coverageには `status` と `searched_paths`、発見時は参照元の `path` を記す。

発見した内容は証拠ではなく探索仮説であることを明記し、親が読んだ履歴を `codebase-consistency-reviewer` / `bug-hunter` / `test-reviewer` にのみ渡す。各subagentには差分外の呼び出し側や対になる実装まで探索し、可能な範囲で検索結果や安全な実行結果を示すよう依頼する。実行不能な場合はその理由を記録する。

## 統合

全結果を受け取ってから重複を統合し、現行コード・要件・既存テストで根拠を確かめる。裏付けのない指摘を除き、残る指摘を Blocking / Should fix / Non-blocking に分類する。各件に該当箇所、発生条件、影響、根拠、発見したagent名を書く。該当がなければ「なし」と書く。

最後に Review coverage として実施した4観点、確認できなかった情報、レビュー範囲を記す。明示的な依頼がない限りコードを修正しない。
