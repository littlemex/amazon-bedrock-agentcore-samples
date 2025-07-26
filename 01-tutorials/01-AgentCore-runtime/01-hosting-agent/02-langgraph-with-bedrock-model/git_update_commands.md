# upstream リポジトリの更新を反映する Git コマンド

以下のコマンドを使用して、upstream リポジトリの最新の変更をローカルリポジトリに反映させることができます。

## 1. upstream リモートの設定確認と追加

まず、upstream リモートが設定されているか確認します：

```bash
git remote -v
```

upstream リモートが表示されない場合は、以下のコマンドで追加します（URL は実際の upstream リポジトリの URL に置き換えてください）：

```bash
git remote add upstream https://github.com/original-owner/original-repository.git
```

## 2. upstream リポジトリから最新の変更を取得

```bash
git fetch upstream
```

## 3. ローカルの main ブランチに切り替え

```bash
git checkout main
```

## 4. upstream の変更をローカルの main ブランチにマージ

```bash
git merge upstream/main
```

## 5. （オプション）変更をあなたのフォークにプッシュ

```bash
git push origin main
```

## すべてを一度に実行するコマンド

以下のコマンドを順番に実行することで、upstream の変更を取り込むことができます：

```bash
git fetch upstream
git checkout main
git merge upstream/main
git push origin main  # オプション：あなたのフォークにも反映させる場合
```

## 注意事項

- ローカルで変更を加えている場合は、先に `git stash` でそれらを退避させるか、コミットしておくことをお勧めします
- コンフリクトが発生した場合は、それらを解決してからマージを完了する必要があります
