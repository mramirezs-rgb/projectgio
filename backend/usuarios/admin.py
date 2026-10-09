from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import UsuarioGIO


@admin.register(UsuarioGIO)
class UsuarioGIOAdmin(UserAdmin):
    list_display = ('expediente', 'first_name', 'last_name', 'rol', 'area_operativa', 'is_active')
    list_filter = ('rol', 'area_operativa', 'is_active', 'is_staff')
    search_fields = ('expediente', 'username', 'first_name', 'last_name', 'email')
    ordering = ('expediente',)
    fieldsets = (
        (None, {'fields': ('expediente', 'username', 'password')}),
        ('Datos personales', {'fields': ('first_name', 'last_name', 'email', 'telefono')}),
        ('Operación GIO', {'fields': ('rol', 'area_operativa')}),
        ('Permisos', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Fechas', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('expediente', 'first_name', 'last_name', 'rol', 'area_operativa',
                       'password1', 'password2'),
        }),
    )
