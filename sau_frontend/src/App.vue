<template>
  <div id="app">
    <el-container class="app-layout">
      <el-aside :width="isCollapse ? '64px' : '184px'" class="app-aside">
        <div class="sidebar" :class="{ collapsed: isCollapse }">
          <div class="logo">
            <div class="logo-badge" aria-label="TaoX AI">
              <span class="logo-word logo-word--brand">TaoX</span>
              <span class="logo-word logo-word--ai">AI</span>
            </div>
          </div>

          <el-menu
            :router="true"
            :default-active="activeMenu"
            :collapse="isCollapse"
            class="sidebar-menu"
            background-color="transparent"
            text-color="#AEBBD0"
            active-text-color="#FFFFFF"
          >
            <el-menu-item index="/">
              <el-icon><HomeFilled /></el-icon>
              <span>首页</span>
            </el-menu-item>
            <el-menu-item index="/account-management">
              <el-icon><User /></el-icon>
              <span>账号管理</span>
            </el-menu-item>
            <el-menu-item index="/material-management">
              <el-icon><Picture /></el-icon>
              <span>素材管理</span>
            </el-menu-item>
            <el-menu-item index="/publish-center">
              <el-icon><Upload /></el-icon>
              <span>发布中心</span>
            </el-menu-item>
            <el-menu-item index="/task-progress">
              <el-icon><Odometer /></el-icon>
              <span>任务进度</span>
            </el-menu-item>
            <el-menu-item index="/ai-publish">
              <el-icon><ChatDotRound /></el-icon>
              <span>AI发布</span>
            </el-menu-item>
            <el-menu-item index="/about">
              <el-icon><DataAnalysis /></el-icon>
              <span>关于</span>
            </el-menu-item>
          </el-menu>

          <button class="sidebar-toggle" type="button" @click="toggleSidebar">
            <el-icon>
              <Expand v-if="isCollapse" />
              <Fold v-else />
            </el-icon>
            <span v-show="!isCollapse">收起边栏</span>
          </button>
        </div>
      </el-aside>

      <el-container>
        <el-main class="app-main">
          <router-view />
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  HomeFilled,
  User,
  DataAnalysis,
  Odometer,
  ChatDotRound,
  Expand,
  Fold,
  Picture,
  Upload
} from '@element-plus/icons-vue'

const route = useRoute()
const activeMenu = computed(() => route.path)
const isCollapse = ref(false)

const toggleSidebar = () => {
  isCollapse.value = !isCollapse.value
}
</script>

<style lang="scss" scoped>
@use '@/styles/variables.scss' as *;

#app {
  height: 100vh;
  min-height: 0;
  overflow: hidden;
}

.app-layout {
  height: 100vh;
  min-height: 0;
  overflow: hidden;

  > .el-container {
    min-width: 0;
    min-height: 0;
    height: 100vh;
  }
}

.app-aside {
  position: relative;
  z-index: 5;
  height: 100vh;
  overflow: hidden;
  color: #fff;
  background: #001529;
  box-shadow: 18px 0 36px rgba(21, 32, 51, 0.06);
  transition: width 0.25s ease;
}

.sidebar {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 0 10px 14px;

  &.collapsed {
    align-items: center;
    padding-inline: 8px;
  }
}

.logo {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 64px;
  margin: 0 -10px 12px;
  padding: 10px 12px 14px;
  overflow: hidden;
  background: transparent;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);

  .logo-badge {
    min-width: 0;
    height: 32px;
    flex: 0 0 auto;
    padding: 0;
    border-radius: 10px;
    background: transparent;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 3px;
    box-shadow: none;
  }

  .logo-word {
    font-size: 15px;
    font-weight: 800;
    line-height: 1;
    letter-spacing: 0;
  }

  .logo-word--brand {
    color: #7860ff;
  }

  .logo-word--ai {
    color: #ffffff;
  }
}

.sidebar-menu {
  flex: 1;
  min-width: 0;
  border-right: none;
  background: transparent;

  :deep(.el-menu) {
    border-right: none;
    background: transparent;
  }

  :deep(.el-menu-item) {
    height: 40px;
    margin: 4px 0;
    padding: 0 12px !important;
    border-radius: 10px;
    color: #aebbd0;
    font-size: 13px;
    transition: background 0.2s ease, color 0.2s ease, transform 0.2s ease;

    .el-icon {
      width: 18px;
      height: 18px;
      margin-right: 10px;
      color: inherit;
    }

    &:hover {
      color: #fff;
      background: rgba(255, 255, 255, 0.06);
    }

    &.is-active {
      color: #fff;
      border: 1px solid #174c7a;
      background: #0b3568;
      box-shadow: none;
    }
  }

  :deep(.el-menu--collapse) {
    width: 48px;
  }

  :deep(.el-menu--collapse .el-menu-item) {
    justify-content: center;
    padding: 0 !important;

    .el-icon {
      margin-right: 0;
    }
  }
}

.sidebar-toggle {
  width: 100%;
  min-height: 40px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.78);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: background 0.2s ease, color 0.2s ease, border-color 0.2s ease;

  .el-icon {
    font-size: 17px;
  }

  span {
    font-size: 13px;
    white-space: nowrap;
  }

  &:hover {
    color: #fff;
    border-color: rgba(96, 165, 250, 0.42);
    background: rgba(47, 109, 246, 0.18);
  }
}

.app-main {
  position: relative;
  height: 100vh;
  min-height: 0;
  padding: 24px 30px;
  overflow-y: auto;
  background: #f3f6fb;

  &::before {
    display: none;
  }

  > * {
    position: relative;
    z-index: 1;
  }
}
</style>
