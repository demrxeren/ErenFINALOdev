<template>
  <el-container class="admin-container">
    <AppSidebar active-index="2" />
    
    <el-container class="main-container">
      <el-header class="admin-header">
        <h2>Admin Panel</h2>
      </el-header>
      
      <el-main>
        <el-card class="user-management-card">
          <template #header>
            <div class="card-header">
              <span>User Management</span>
            </div>
          </template>
          
          <el-form :model="userForm" ref="userFormRef" :rules="userRules" label-width="120px">
            <el-form-item label="Username" prop="username">
              <el-input v-model="userForm.username" placeholder="Enter username" />
            </el-form-item>
            <el-form-item label="Password" prop="password">
              <el-input v-model="userForm.password" type="password" placeholder="Enter password" show-password />
            </el-form-item>
            <el-form-item label="Admin Role">
              <el-switch v-model="userForm.is_admin" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="addUser">
                <el-icon><Plus /></el-icon>
                Add New User
              </el-button>
            </el-form-item>
          </el-form>
          
          <el-divider />
          
          <h3>Existing Users</h3>
          <el-table :data="users" style="width: 100%" stripe>
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="username" label="Username" />
            <el-table-column prop="is_admin" label="Role" width="150">
              <template #default="{ row }">
                <el-tag :type="row.is_admin ? 'danger' : 'success'" effect="dark">
                  {{ row.is_admin ? 'Admin' : 'User' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="Actions" width="120" align="center">
              <template #default="{ row }">
                <el-button 
                  v-if="row.username !== 'admin'" 
                  type="danger" 
                  size="small" 
                  circle
                  :icon="Delete"
                  @click="deleteUser(row.id)"
                />
                <el-tag v-else type="info" size="small">Protected</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete } from '@element-plus/icons-vue'
import AppSidebar from '../components/AppSidebar.vue'

const users = ref([]), userFormRef = ref(null),
      userForm = reactive({ username: '', password: '', is_admin: false }),
      userRules = {
        username: [{ required: true, message: 'Username is required', trigger: 'blur' }],
        password: [
          { required: true, message: 'Password is required', trigger: 'blur' },
          { min: 6, message: 'Password must be at least 6 characters', trigger: 'blur' }
        ]
      }

const fetchUsers = async () => {
  try {
    const { data } = await axios.get('https://conspiringly-desmotropic-tyisha.ngrok-free.dev/api/users', { withCredentials: true })
    users.value = data
  } catch { ElMessage.error('Failed to load users') }
}

const addUser = async () => {
  await userFormRef.value?.validate(async (valid) => {
    if (!valid) return
    try {
      await axios.post('https://conspiringly-desmotropic-tyisha.ngrok-free.dev/api/users', userForm, { withCredentials: true })
      ElMessage.success('User added successfully')
      Object.assign(userForm, { username: '', password: '', is_admin: false })
      fetchUsers()
    } catch (e) { ElMessage.error(e.response?.data?.error || 'Failed to add user') }
  })
}

const deleteUser = async (id) => {
  try {
    await ElMessageBox.confirm('Are you sure you want to delete this user?', 'Warning', {
      confirmButtonText: 'Yes, Delete', cancelButtonText: 'Cancel', type: 'warning' })
    await axios.delete(`https://conspiringly-desmotropic-tyisha.ngrok-free.dev/api/users/${id}`, { withCredentials: true })
    ElMessage.success('User deleted successfully'); fetchUsers()
  } catch (e) { if (e !== 'cancel') ElMessage.error('Failed to delete user') }
}

onMounted(fetchUsers)
</script>

<style scoped>
.admin-container {
  min-height: 100vh;
  background: #e4e7ed;
}

.main-container {
  flex: 1;
}

.admin-header {
  background: white;
  display: flex;
  align-items: center;
  padding: 0 32px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.admin-header h2 {
  margin: 0;
  color: #303133;
}

.user-management-card {
  margin: 24px;
}

.card-header {
  font-size: 18px;
  font-weight: bold;
  color: #303133;
}

h3 {
  margin: 20px 0 16px 0;
  color: #303133;
}
</style>
