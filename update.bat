@echo off
chcp 65001 > nul
echo 🧁 Синхронизируем вкусняшки с Vercel...
git add products.json
git commit -m "Auto-update menu"
git push origin main
echo 🎉 Витрина успешно обновлена!
pause