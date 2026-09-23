<script setup>
import { ref } from 'vue';
import { useAuth } from '../composables/useAuth';

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
          ⚠️ {{ errorLogin }}
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

<style scoped>
.login-wrapper {
  min-height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: #0f172a;
  padding: 1rem;
}

.login-card {
  background-color: #1e293b;
  border: 1px solid #334155;
  border-radius: 12px;
  width: 100%;
  max-width: 420px;
  padding: 2.5rem;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
  color: #f8fafc;
}

.login-header {
  text-align: center;
  margin-bottom: 2rem;
}

.logo-badge {
  display: inline-block;
  background-color: #2563eb;
  color: #ffffff;
  font-weight: 900;
  font-size: 1.25rem;
  padding: 0.4rem 1rem;
  border-radius: 8px;
  margin-bottom: 0.8rem;
  letter-spacing: 2px;
}

.login-header h2 {
  margin: 0;
  font-size: 1.5rem;
  color: #f8fafc;
}

.subtitle {
  margin-top: 0.4rem;
  font-size: 0.8rem;
  color: #94a3b8;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 1.2rem;
}

.error-banner {
  background-color: rgba(239, 68, 68, 0.2);
  border: 1px solid #ef4444;
  color: #f87171;
  padding: 0.75rem;
  border-radius: 6px;
  font-size: 0.8rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.form-group label {
  font-size: 0.8rem;
  color: #94a3b8;
  font-weight: 600;
}

.form-group input {
  background-color: #0f172a;
  border: 1px solid #334155;
  border-radius: 6px;
  padding: 0.75rem 1rem;
  color: #f8fafc;
  font-size: 0.95rem;
  outline: none;
  transition: border-color 0.2s;
}

.form-group input:focus {
  border-color: #38bdf8;
}

.btn-login {
  margin-top: 0.5rem;
  background-color: #2563eb;
  color: #ffffff;
  border: none;
  padding: 0.8rem;
  border-radius: 6px;
  font-weight: 700;
  font-size: 0.95rem;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-login:hover:not(:disabled) {
  background-color: #1d4ed8;
}

.btn-login:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* DEMO ROLES */
.demo-roles {
  margin-top: 2rem;
  padding-top: 1.5rem;
  border-top: 1px solid #334155;
  text-align: center;
}

.demo-roles small {
  color: #64748b;
  font-size: 0.75rem;
  display: block;
  margin-bottom: 0.6rem;
}

.role-buttons {
  display: flex;
  gap: 0.5rem;
  justify-content: center;
}

.btn-role {
  background-color: #0f172a;
  border: 1px solid #334155;
  color: #94a3b8;
  padding: 0.35rem 0.6rem;
  border-radius: 4px;
  font-size: 0.7rem;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-role:hover {
  border-color: #38bdf8;
  color: #38bdf8;
}
</style>