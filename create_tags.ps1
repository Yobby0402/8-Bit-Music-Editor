# 创建标签和提交的脚本
git tag v3.0.0 v2.4
git add -A
git commit -m "v3.1.0: Add Intro/Main structure, style variants, and style parameter visualization"
git tag v3.1.0
git push origin v3.0.0 v3.1.0
git push origin dev-V2.3
Write-Host "完成！已创建 v3.0.0 和 v3.1.0 标签并推送到 GitHub"

