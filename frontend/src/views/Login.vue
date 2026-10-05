<script setup>
import { ref } from 'vue';
import { useAuth } from '../composables/useAuth';
import '../assets/loginstyle.css'
const expediente = ref('');
const password = ref('');
const { iniciarSesion, cargando, errorLogin } = useAuth();
const handleSubmit = async () => {
  if (!expediente.value || !password.value) return;
  await iniciarSesion(expediente.value, password.value);
};
// Accesos rápidos para probar diferentes roles durante el desarrollo
const probarComo = (rol) => {
  if (rol === 'PI') { expediente.value = 'OQU-8821'; password.value = '123456'; }
  if (rol === 'PE') { expediente.value = 'TEC-4410'; password.value = '123456'; }
  if (rol === 'ADMIN') { expediente.value = 'JEFE-001'; password.value = '123456'; }
  handleSubmit();
};
</script>
<template>
  <div class="login-wrapper">
    <div class="login-card">
      <header class="login-header">
        <div class="logo-badge">GIO</div>
        <h2>GIO TELMEX</h2>
        <p class="subtitle">CASE Puebla — Gestión de Incidencias Operativas</p>
      </header>
      <form @submit.prevent="handleSubmit" class="login-form">
        <div v-if="errorLogin" class="error-banner">
          {{ errorLogin }}
        </div>
        <div class="form-group">
          <label>Expediente / Usuario</label>
          <input 
            v-model="expediente" 
            type="text" 
            placeholder="Ej. OQU-9921" 
            required 
            autocomplete="username"
          />
        </div>
        <div class="form-group">
          <label>Contraseña</label>
          <input 
            v-model="password" 
            type="password" 
            placeholder="••••••••" 
            required 
            autocomplete="current-password"
          />
        </div>
        <button type="submit" class="btn-login" :disabled="cargando">
          <span v-if="!cargando">Iniciar Sesión</span>
          <span v-else>Autenticando...</span>
        </button>
      </form>
      <!-- BOTONES DE PRUEBA RÁPIDA (SOLO PARA DESARROLLO) -->
      <div class="demo-roles">
        <small>Probar acceso como:</small>
        <div class="role-buttons">
          <button @click="probarComo('PI')" type="button" class="btn-role">Planta Interna</button>
          <button @click="probarComo('PE')" type="button" class="btn-role">Técnico PE</button>
          <button @click="probarComo('ADMIN')" type="button" class="btn-role">Jefatura</button>
        </div>
      </div>
    </div>
  </div>
</template>