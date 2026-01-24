class YuklamaSorov(models.Model):
    ST_CHOICES = (
        ('done', 'Done'),
        ('waiting', 'kutilmoqda'),
        ('rejected', 'Rad etildi'),
    )
    id=models.AutoField(primary_key=True)
    mode=models.CharField(max_length=20, choices=ST_CHOICES)
    pazanda=models.ForeignKey(Pazanda, on_delete=models.CASCADE, null=True, blank=True)
    user=models.ForeignKey(YetkazibBeruvchi, on_delete=models.CASCADE)
    mahsulot=models.ForeignKey(Mahsulot, on_delete=models.CASCADE, null=True, blank=True)
    miqdor = models.FloatField()
    sana = models.DateTimeField(auto_now_add=True)
    tasdiq=models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.user.login} - {self.miqdor}"

# --- NASIYA TO'LOV ---
class NasiyaTolov(models.Model):
    savdo = models.ForeignKey(Savdo, on_delete=models.CASCADE, related_name='to\'lovlar')
    tolov_summasi = models.FloatField()
    tolov_sanasi = models.DateTimeField(auto_now_add=True)
    izoh = models.TextField(blank=True, null=True)
    qabul_qilgan_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.savdo.haridor_dukon.nomi} - {self.tolov_summasi}"

    class Meta:
        verbose_name = "Nasiya To'lov"
        verbose_name_plural = "Nasiya To'lovlar"
        ordering = ['-tolov_sanasi']
