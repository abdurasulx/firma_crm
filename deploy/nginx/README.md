# StockFirm Nginx Deploy

These configs assume:

- Project deploy path: `/var/www/stockfirm`
- Django/ASGI server: `127.0.0.1:8000`
- Domain: `stockfirm.uz`
- Wildcard tenant domains: `*.stockfirm.uz`
- Static root after `collectstatic`: `/var/www/stockfirm/staticfiles`
- Media root: `/var/www/stockfirm/media`

Install:

```bash
sudo cp deploy/nginx/nginx-http-limits.conf /etc/nginx/snippets/stockfirm-http-limits.conf
sudo cp deploy/nginx/stockfirm.conf /etc/nginx/sites-available/stockfirm.conf
sudo ln -s /etc/nginx/sites-available/stockfirm.conf /etc/nginx/sites-enabled/stockfirm.conf
```

Add this inside the `http { ... }` block in `/etc/nginx/nginx.conf`:

```nginx
include /etc/nginx/snippets/stockfirm-http-limits.conf;
```

Test and reload:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

DNS records required:

```text
A      stockfirm.uz        SERVER_IP
A      www.stockfirm.uz    SERVER_IP
A      admin.stockfirm.uz  SERVER_IP
A      *.stockfirm.uz      SERVER_IP
```

Wildcard SSL:

```bash
sudo certbot certonly --manual --preferred-challenges dns -d stockfirm.uz -d '*.stockfirm.uz'
```

Important Django env:

```env
DEBUG=False
ALLOWED_HOSTS=stockfirm.uz,www.stockfirm.uz,admin.stockfirm.uz,.stockfirm.uz
CSRF_TRUSTED_ORIGINS=https://stockfirm.uz,https://www.stockfirm.uz,https://admin.stockfirm.uz,https://*.stockfirm.uz
```
