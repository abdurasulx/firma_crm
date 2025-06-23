def mahsulotlar_miqdori(mahstr):
    from collections import defaultdict

    if not mahstr:
        return {}

    natija = defaultdict(int)
    mahsulotlar = [item.strip() for item in mahstr.split(',') if item.strip()]
    
    for mahsulot in mahsulotlar:
        qismlar = mahsulot.rsplit(' ', 1)
        if len(qismlar) == 2:
            nomi, miqdori = qismlar
            try:
                natija[nomi.strip()] += int(miqdori.strip())
            except ValueError:
                pass  # Agar son bo'lmasa, o'tkazib yuboramiz
    
    return dict(natija)
