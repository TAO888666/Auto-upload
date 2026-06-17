<template>
  <div class="publish-center">
    <div v-if="false" class="page-header publish-header">
      <h1>发布中心</h1>
    </div>

    <!-- Tab管理区域 -->
    <div class="tab-management">
      <div class="tab-header">
        <div class="tab-list">
          <div 
            v-for="tab in tabs" 
            :key="tab.name"
            :class="['tab-item', { active: activeTab === tab.name }]"
            @click="activeTab = tab.name"
          >
            <span>{{ tab.label }}</span>
            <el-icon 
              v-if="tabs.length > 1"
              class="close-icon" 
              @click.stop="removeTab(tab.name)"
            >
              <Close />
            </el-icon>
          </div>
        </div>
        <div class="tab-actions">
          <el-button
            size="small"
            :type="globalPublishMode === 'headed' ? 'success' : 'danger'"
            class="global-publish-mode-btn"
            @click="toggleGlobalPublishMode"
          >
            {{ globalPublishMode === 'headed' ? '发布显示' : '发布隐身' }}
          </el-button>
          <el-button
            size="small"
            plain
            @click="clearAllPublishDrafts({ preserveOneTab: true })"
            class="clear-draft-btn"
          >
            清空草稿
          </el-button>
          <el-button 
            type="primary" 
            size="small" 
            @click="addTab"
            class="add-tab-btn"
          >
            <el-icon><Plus /></el-icon>
            添加Tab
          </el-button>
          <el-button
            type="primary"
            plain
            size="small"
            @click="generatePublishCopy"
            :loading="globalAiGenerating"
            :disabled="!hasAIGeneratableTabs"
            class="global-ai-generate-btn"
          >
            AI生成
          </el-button>
          <el-button 
            type="success" 
            size="small" 
            @click="batchPublish"
            :loading="batchPublishing"
            class="batch-publish-btn"
          >
            批量发布
          </el-button>
        </div>
      </div>
    </div>

    <!-- 内容区域 -->
    <div class="publish-content">
      <div class="tab-content-wrapper">
        <div 
          v-for="tab in tabs" 
          :key="tab.name"
          v-show="activeTab === tab.name"
          class="tab-content"
        >
          <!-- 发布状态提示 -->
          <div v-if="tab.publishStatus" class="publish-status">
            <el-alert
              :title="tab.publishStatus.message"
              :type="tab.publishStatus.type"
              :closable="false"
              show-icon
            />
          </div>

          <!-- 视频上传区域 -->
          <div v-if="false" class="upload-section">
            <h3>视频</h3>
            <div class="upload-options">
              <el-button type="primary" @click="showUploadOptions(tab)" class="upload-btn">
                <el-icon><Upload /></el-icon>
                上传视频
              </el-button>
            </div>
            
            <!-- 已上传文件列表 -->
            <div v-if="tab.fileList.length > 0" class="uploaded-files">
              <h4>已上传文件：</h4>
              <div class="file-list">
                <div v-for="(file, index) in tab.fileList" :key="index" class="file-item">
                  <el-link v-if="file.url" :href="file.url" target="_blank" type="primary">{{ file.name }}</el-link>
                  <span v-else class="file-name">{{ file.name }}</span>
                  <el-tag size="small" :type="file.entryKind === 'note' ? 'success' : 'primary'">
                    {{ file.entryKind === 'note' ? '图文作品' : '视频作品' }}
                  </el-tag>
                  <span v-if="file.entryKind === 'note'" class="file-detail">{{ file.files?.length || 0 }} 张图片</span>
                  <span class="file-size">{{ (file.size / 1024 / 1024).toFixed(2) }}MB</span>
                  <el-button type="danger" size="small" @click="removeFile(tab, index)">删除</el-button>
                </div>
              </div>
            </div>
          </div>

          <!-- 上传选项弹窗 -->
          <el-dialog
            v-model="uploadOptionsVisible"
            title="选择上传方式"
            width="400px"
            class="upload-options-dialog"
          >
            <div class="upload-options-content">
              <el-button type="primary" @click="selectLocalUpload" class="option-btn">
                <el-icon><Upload /></el-icon>
                本地上传
              </el-button>
              <el-button type="success" @click="selectMaterialLibrary" class="option-btn">
                <el-icon><Folder /></el-icon>
                素材库
              </el-button>
            </div>
          </el-dialog>

          <!-- 本地上传弹窗 -->
          <el-dialog
            v-model="localUploadVisible"
            title="本地上传"
            width="600px"
            class="local-upload-dialog"
          >
            <div class="folder-upload-actions">
              <el-button type="success" plain @click="openFolderUploadPicker" :loading="folderUploading">
                选择图片文件夹
              </el-button>
              <span class="folder-upload-tip">单个视频文件会识别成视频作品，单个图片文件夹会识别成图文作品。</span>
              <input
                ref="uploadFilesInput"
                type="file"
                multiple
                accept="video/*,image/*"
                class="folder-upload-input"
                @change="handleFileUploadChange"
              >
              <input
                ref="folderUploadInput"
                type="file"
                webkitdirectory
                directory
                multiple
                class="folder-upload-input"
                @change="handleDirectoryUploadChange"
              >
            </div>
            <el-upload
              class="video-upload"
              drag
              :auto-upload="false"
              :show-file-list="false"
              multiple
              accept="video/*,image/*"
              @dragover.stop.prevent
              @drop.stop.prevent="handleCustomUploadDrop"
            >
              <el-icon class="el-icon--upload"><Upload /></el-icon>
              <div class="el-upload__text">
                将视频文件拖到此处，或<em>点击上传</em>
              </div>
              <div class="custom-upload-directory-entry">
                <button type="button" class="directory-entry-btn" @click.stop.prevent="openDirectoryUploadPicker">
                  导入目录
                </button>
              </div>
              <template #tip>
                <div class="el-upload__tip">
                  支持MP4、AVI等视频格式，可上传多个文件
                </div>
              </template>
              <div
                class="custom-upload-overlay"
                @click.stop.prevent="openFileUploadPicker"
                @dragover.stop.prevent
                @drop.stop.prevent="handleCustomUploadDrop"
              />
            </el-upload>
          </el-dialog>

          <!-- 素材库选择弹窗 -->
          <el-dialog
            v-model="uploadMethodVisible"
            title="选择上传方式"
            width="360px"
            class="upload-method-dialog"
          >
            <div class="upload-method-actions">
              <el-button type="primary" @click="openFileUploadPicker">
                选择文件
              </el-button>
              <el-button type="success" plain @click="openDirectoryUploadPicker" :loading="folderUploading">
                导入目录
              </el-button>
            </div>
          </el-dialog>

          <el-dialog
            v-model="materialLibraryVisible"
            title="选择素材"
            width="800px"
            class="material-library-dialog"
          >
            <div class="material-library-content">
              <el-checkbox-group v-model="selectedMaterials">
                <div class="material-list">
                  <div
                    v-for="material in materials"
                    :key="material.id"
                    class="material-item"
                  >
                    <el-checkbox :label="material.id" class="material-checkbox">
                      <div class="material-info">
                        <div class="material-name">{{ material.filename }}</div>
                        <div class="material-details">
                          <span class="file-size">{{ material.filesize }}MB</span>
                          <span class="upload-time">{{ material.upload_time }}</span>
                        </div>
                      </div>
                    </el-checkbox>
                  </div>
                </div>
              </el-checkbox-group>
            </div>
            <template #footer>
              <div class="dialog-footer">
                <el-button @click="materialLibraryVisible = false">取消</el-button>
                <el-button type="primary" @click="confirmMaterialSelection">确定</el-button>
              </div>
            </template>
          </el-dialog>

          <!-- 账号选择 -->
          <div v-if="false" class="account-section">
            <h3>账号</h3>
            <div class="account-display">
              <div class="selected-accounts">
                <el-tag
                  v-for="(account, index) in tab.selectedAccounts"
                  :key="index"
                  closable
                  @close="removeAccount(tab, index)"
                  class="account-tag"
                >
                  {{ getAccountDisplayName(account) }}
                </el-tag>
              </div>
              <el-button 
                type="primary" 
                plain 
                @click="openAccountDialog(tab)"
                class="select-account-btn"
              >
                选择账号
              </el-button>
            </div>
          </div>

          <!-- 账号选择弹窗 -->
          <el-dialog
            v-model="accountDialogVisible"
            title="选择账号"
            width="600px"
            class="account-dialog"
          >
            <div class="account-dialog-content">
              <el-checkbox-group v-model="tempSelectedAccounts">
                <div class="account-list">
                  <el-checkbox
                    v-for="account in availableAccounts"
                    :key="account.id"
                    :label="account.id"
                    class="account-item"
                  >
                    <div class="account-info">
                      <span class="account-name">{{ account.name }}</span>
                      <span class="account-platform">{{ account.platform }}</span>
                    </div>
                  </el-checkbox>
                </div>
              </el-checkbox-group>
            </div>

            <template #footer>
              <div class="dialog-footer">
                <el-button @click="accountDialogVisible = false">取消</el-button>
                <el-button type="primary" @click="confirmAccountSelection">确定</el-button>
              </div>
            </template>
          </el-dialog>

          <!-- 原创声明 -->
          <el-dialog
            v-model="publishAccountLoginDialogVisible"
            title="账号登录"
            width="420px"
            v-if="false"
            class="account-login-dialog"
            :close-on-click-modal="false"
          >
            <div class="account-login-dialog-content">
              <p class="account-login-dialog-title">
                请在已打开的浏览器窗口完成
                <span>{{ publishAccountLoginTarget?.name || '当前账号' }}</span>
                的登录。
              </p>
              <p class="account-login-dialog-tip">
                完成扫码或授权后，点击下方“我已完成登录”，系统会自动保存 Cookie 并刷新这个账号状态。
              </p>
            </div>
            <template #footer>
              <div class="dialog-footer">
                <el-button @click="closePublishAccountLoginDialog">取消</el-button>
                <el-button
                  type="primary"
                  :loading="publishAccountLoginConfirming"
                  @click="confirmPublishAccountLogin"
                >
                  {{ publishAccountLoginConfirming ? '确认中...' : '我已完成登录' }}
                </el-button>
              </div>
            </template>
          </el-dialog>

          <!-- publish-center account login dialog -->
          <el-dialog
            v-model="publishAccountLoginDialogVisible"
            :title="publishAccountLoginDialogTitle"
            width="420px"
            class="account-login-dialog"
            :close-on-click-modal="false"
          >
            <div class="account-login-dialog-content">
              <p class="account-login-dialog-title">
                {{ publishAccountLoginDialogLeadPrefix }}
                <span>{{ publishAccountLoginTarget?.name || publishAccountLoginDialogFallbackName }}</span>
                {{ publishAccountLoginDialogLeadSuffix }}
              </p>
              <p class="account-login-dialog-tip">{{ publishAccountLoginDialogTip }}</p>
            </div>
            <template #footer>
              <div class="dialog-footer">
                <el-button @click="closePublishAccountLoginDialog">{{ commonCancelText }}</el-button>
                <el-button
                  type="primary"
                  :loading="publishAccountLoginConfirming"
                  @click="confirmPublishAccountLogin"
                >
                  {{ publishAccountLoginConfirming ? publishAccountLoginConfirmingText : publishAccountLoginConfirmText }}
                </el-button>
              </div>
            </template>
          </el-dialog>

          <div v-if="false" class="original-section">
            <el-checkbox
              v-model="tab.isOriginal"
              label="声明原创"
              class="original-checkbox"
            />
            <el-checkbox
              v-if="tabHasSelectedPlatform(tab, 3)"
              v-model="tab.douyinSelfDeclaration"
              label="自主声明"
              class="original-checkbox"
            />
          </div>

          <div class="publish-workspace">
            <aside class="account-sidebar">
              <div class="sidebar-panel-header">
                <div>
                  <h3>选择账号</h3>
                  <p>已选 {{ tab.selectedAccounts.length }} 个账号</p>
                </div>
              </div>
              <div class="account-sidebar-filters">
                <div class="account-sidebar-search-row">
                  <el-input
                    v-model="accountSidebarKeyword"
                    class="account-search-input"
                    placeholder="搜索账号"
                    clearable
                  />
                </div>
                <div class="account-sidebar-select-row">
                  <el-select
                    v-model="accountSidebarPlatformFilter"
                    class="account-platform-filter"
                    placeholder="全部平台"
                  >
                    <el-option label="全部平台" value="all" />
                    <el-option
                      v-for="platform in accountSidebarPlatforms"
                      :key="platform"
                      :label="platform"
                      :value="platform"
                    />
                  </el-select>
                  <el-select
                    v-model="accountSidebarGroupFilter"
                    class="account-group-filter"
                    placeholder="全部分组"
                  >
                    <el-option label="全部分组" value="all" />
                    <el-option
                      v-for="group in accountSidebarGroups"
                      :key="group.id"
                      :label="group.name"
                      :value="group.id"
                    />
                  </el-select>
                </div>
              </div>
              <div class="account-sidebar-list">
                <div
                  v-for="account in filteredSidebarAccounts(tab)"
                  :key="account.id"
                  class="account-sidebar-item"
                  :class="{
                    selected: isSidebarAccountSelected(tab, account.id),
                    'selected-in-other-tab': isSidebarAccountSelectedInOtherTabs(tab, account.id)
                  }"
                  @click="toggleSidebarAccountSelection(tab, account.id)"
                >
                  <el-avatar :src="getPublishAccountAvatar(account)" class="account-sidebar-avatar">
                    {{ String(account.name || '').slice(0, 1) }}
                  </el-avatar>
                  <div class="account-sidebar-meta">
                    <span class="account-sidebar-name">{{ account.name }}</span>
                    <span class="account-sidebar-status" :class="{ invalid: account.status !== STATUS_LABEL_NORMAL }">
                      {{ account.status }}
                    </span>
                  </div>
                  <div class="account-sidebar-actions">
                    <el-tag size="small" effect="plain" class="account-sidebar-platform-tag">
                      {{ account.platform }}
                    </el-tag>
                    <el-button
                      link
                      size="small"
                      :type="account.status === STATUS_LABEL_NORMAL ? 'success' : 'danger'"
                      class="account-sidebar-action-btn"
                      :loading="isSidebarAccountActionLoading(account)"
                      @click.stop="handleSidebarAccountAction(account)"
                    >
                      {{ getSidebarAccountActionLabel(account) }}
                    </el-button>
                  </div>
                  <el-checkbox
                    class="account-sidebar-check"
                    :model-value="isSidebarAccountSelected(tab, account.id) || isSidebarAccountSelectedInOtherTabs(tab, account.id)"
                    @change="toggleSidebarAccountSelection(tab, account.id)"
                    @click.stop
                  />
                </div>
                <el-empty
                  v-if="filteredSidebarAccounts(tab).length === 0"
                  description="没有匹配的账号"
                  :image-size="72"
                />
              </div>
            </aside>

            <section class="upload-stage-panel">
              <div class="panel-header">
                <div>
                  <h3>上传作品</h3>
                  <p>上传后会显示本地文件名，方便核对当前 Tab 的作品清单。</p>
                </div>
              </div>
              <div class="upload-section upload-section--panel" :class="{ 'is-empty': tab.fileList.length === 0 }">
                <div class="upload-stage-body">
                  <div class="upload-options">
                    <el-button type="primary" @click="showUploadOptions(tab)" class="upload-btn">
                      <el-icon><Upload /></el-icon>
                      上传视频
                    </el-button>
                    <p class="upload-stage-tip">支持视频与图文作品，上传后可继续在右侧补标题、文案与定时设置。</p>
                  </div>

                  <div v-if="tab.fileList.length > 0" class="uploaded-files">
                    <h4>已上传作品</h4>
                    <div class="file-list">
                      <div v-for="(file, index) in tab.fileList" :key="index" class="file-item">
                        <el-link v-if="file.url" :href="file.url" target="_blank" type="primary">{{ file.name }}</el-link>
                        <span v-else class="file-name">{{ file.name }}</span>
                        <el-tag size="small" :type="file.entryKind === 'note' ? 'success' : 'primary'">
                          {{ file.entryKind === 'note' ? '图文作品' : '视频作品' }}
                        </el-tag>
                        <span v-if="file.entryKind === 'note'" class="file-detail">{{ file.files?.length || 0 }} 张图片</span>
                        <span class="file-size">{{ (file.size / 1024 / 1024).toFixed(2) }}MB</span>
                        <el-button type="danger" size="small" @click="removeFile(tab, index)">删除</el-button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            <section class="content-config-panel">
              <div class="content-config-scroll">
                <div class="original-section">
                  <el-checkbox
                    v-model="tab.isOriginal"
                    label="声明原创"
                    class="original-checkbox"
                  />
                  <el-checkbox
                    v-model="tab.douyinSelfDeclaration"
                    label="自主声明"
                    class="original-checkbox"
                  />
                </div>

                <div v-if="tabHasSelectedPlatform(tab, 2)" class="draft-section">
                  <el-checkbox
                    v-model="tab.isDraft"
                    label="视频号仅保存草稿(用手机发布)"
                    class="draft-checkbox"
                  />
                </div>

                <div class="product-section">
                  <h3>商品链接</h3>
                  <el-input
                    v-model="tab.productTitle"
                    type="text"
                    :rows="1"
                    placeholder="请输入商品名称"
                    maxlength="200"
                    class="product-name-input"
                  />
                  <el-input
                    v-model="tab.productLink"
                    type="text"
                    :rows="1"
                    placeholder="请输入商品链接"
                    maxlength="200"
                    class="product-link-input"
                  />
                </div>

                <div class="title-section">
                  <h3>标题</h3>
                  <el-input
                    v-model="tab.title"
                    type="textarea"
                    :rows="3"
                    placeholder="请输入标题，多作品时用空行分隔一个作品"
                    class="title-input"
                  />
                </div>

                <div class="content-section">
                  <h3>文案</h3>
                  <el-input
                    v-model="tab.content"
                    type="textarea"
                    :rows="5"
                    placeholder="请输入文案，多作品时用空行分隔一个作品"
                    class="content-input"
                  />
                </div>

                <div class="topic-section">
                  <h3>话题</h3>
                  <div class="topic-display">
                    <div class="selected-topics">
                      <el-tag
                        v-for="(topic, index) in tab.selectedTopics"
                        :key="index"
                        closable
                        @close="removeTopic(tab, index)"
                        class="topic-tag"
                      >
                        #{{ topic }}
                      </el-tag>
                    </div>
                    <el-button
                      type="primary"
                      plain
                      @click="openTopicDialog(tab)"
                      class="select-topic-btn"
                    >
                      添加话题
                    </el-button>
                  </div>
                </div>

                <div class="schedule-section">
                  <h3>定时发布</h3>
                  <div class="schedule-controls">
                    <el-switch
                      v-model="tab.scheduleEnabled"
                      active-text="定时发布"
                      inactive-text="立即发布"
                    />
                    <div v-if="tab.scheduleEnabled" class="schedule-settings">
                      <div class="schedule-item">
                        <span class="label">每天发布视频数：</span>
                        <el-select v-model="tab.videosPerDay" placeholder="选择发布数量">
                          <el-option
                            v-for="num in 55"
                            :key="num"
                            :label="num"
                            :value="num"
                          />
                        </el-select>
                      </div>
                      <div class="schedule-item">
                        <span class="label">每天发布时间：</span>
                        <el-time-select
                          v-for="(time, index) in tab.dailyTimes"
                          :key="index"
                          v-model="tab.dailyTimes[index]"
                          start="00:00"
                          step="00:30"
                          end="23:30"
                          placeholder="选择时间"
                        />
                        <el-button
                          v-if="tab.dailyTimes.length < tab.videosPerDay"
                          type="primary"
                          size="small"
                          @click="tab.dailyTimes.push('10:00')"
                        >
                          添加时间
                        </el-button>
                      </div>
                      <div class="schedule-item">
                        <span class="label">开始天数：</span>
                        <el-input-number v-model="tab.startDays" :min="0" :step="1" :precision="0" />
                        <span class="schedule-tip">0=现在，1=明天，2=后天...</span>
                      </div>
                    </div>
                  </div>
                </div>

                <div class="action-buttons">
                  <el-button size="small" @click="cancelPublish(tab)">取消</el-button>
                  <el-button
                    size="small"
                    type="primary"
                    @click="confirmPublish(tab)"
                    :loading="tab.publishing || false"
                  >
                    {{ tab.publishing ? '发布中...' : '发布' }}
                  </el-button>
                </div>
              </div>
            </section>
          </div>

          <!-- 草稿选项 (仅在视频号可见) -->
          <div v-if="false && tabHasSelectedPlatform(tab, 2)" class="draft-section">
            <el-checkbox
              v-model="tab.isDraft"
              label="视频号仅保存草稿(用手机发布)"
              class="draft-checkbox"
            />
          </div>

          <!-- 标签 (仅在抖音可见) -->
          <div v-if="false && tabHasSelectedPlatform(tab, 3)" class="product-section">
            <h3>商品链接</h3>
            <el-input
              v-model="tab.productTitle"
              type="text"
              :rows="1"
              placeholder="请输入商品名称"
              maxlength="200"
              class="product-name-input"
            />
            <el-input
              v-model="tab.productLink"
              type="text"
              :rows="1"
              placeholder="请输入商品链接"
              maxlength="200"
              class="product-link-input"
            />
          </div>

          <!-- 标题输入 -->
          <div v-if="false" class="title-section">
            <h3>标题</h3>
              <el-input
                v-model="tab.title"
                type="textarea"
                :rows="3"
                placeholder="请输入标题，多作品时用空行分隔一个作品"
                class="title-input"
              />
          </div>

          <!-- 话题输入 -->
          <div v-if="false" class="content-section">
            <h3>文案</h3>
            <el-input
              v-model="tab.content"
              type="textarea"
              :rows="5"
              placeholder="请输入文案，多作品时用空行分隔一个作品"
              class="content-input"
            />
          </div>

          <div v-if="false" class="topic-section">
            <h3>话题</h3>
            <div class="topic-display">
              <div class="selected-topics">
                <el-tag
                  v-for="(topic, index) in tab.selectedTopics"
                  :key="index"
                  closable
                  @close="removeTopic(tab, index)"
                  class="topic-tag"
                >
                  #{{ topic }}
                </el-tag>
              </div>
              <el-button 
                type="primary" 
                plain 
                @click="openTopicDialog(tab)"
                class="select-topic-btn"
              >
                添加话题
              </el-button>
            </div>
          </div>

          <!-- 添加话题弹窗 -->
          <el-dialog
            v-model="topicDialogVisible"
            title="添加话题"
            width="600px"
            class="topic-dialog"
          >
            <div class="topic-dialog-content">
              <!-- 自定义话题输入 -->
              <div class="custom-topic-input">
                <el-input
                  v-model="customTopic"
                  placeholder="输入自定义话题"
                  class="custom-input"
                >
                  <template #prepend>#</template>
                </el-input>
                <el-button type="primary" @click="addCustomTopic">添加</el-button>
              </div>

              <!-- 推荐话题 -->
              <div class="recommended-topics">
                <h4>推荐话题</h4>
                <div class="topic-grid">
                  <div
                    v-for="topic in recommendedTopics"
                    :key="topic"
                    class="topic-item"
                  >
                    <el-button
                      :type="currentTab?.selectedTopics?.includes(topic) ? 'primary' : 'default'"
                      @click="toggleRecommendedTopic(topic)"
                      class="topic-btn"
                    >
                      {{ topic }}
                    </el-button>
                    <el-button
                      circle
                      class="delete-topic-btn"
                      @click.stop="removeRecommendedTopicFromLibrary(topic)"
                    >
                      <el-icon><Close /></el-icon>
                    </el-button>
                  </div>
                </div>
              </div>
            </div>

            <template #footer>
              <div class="dialog-footer">
                <el-button @click="topicDialogVisible = false">取消</el-button>
                <el-button type="primary" @click="confirmTopicSelection">确定</el-button>
              </div>
            </template>
          </el-dialog>

          <!-- 定时发布 -->
          <div v-if="false" class="schedule-section">
            <h3>定时发布</h3>
            <div class="schedule-controls">
              <el-switch
                v-model="tab.scheduleEnabled"
                active-text="定时发布"
                inactive-text="立即发布"
              />
              <div v-if="tab.scheduleEnabled" class="schedule-settings">
                <div class="schedule-item">
                  <span class="label">每天发布视频数：</span>
                  <el-select v-model="tab.videosPerDay" placeholder="选择发布数量">
                    <el-option
                      v-for="num in 55"
                      :key="num"
                      :label="num"
                      :value="num"
                    />
                  </el-select>
                </div>
                <div class="schedule-item">
                  <span class="label">每天发布时间：</span>
                  <el-time-select
                    v-for="(time, index) in tab.dailyTimes"
                    :key="index"
                    v-model="tab.dailyTimes[index]"
                    start="00:00"
                    step="00:30"
                    end="23:30"
                    placeholder="选择时间"
                  />
                  <el-button
                    v-if="tab.dailyTimes.length < tab.videosPerDay"
                    type="primary"
                    size="small"
                    @click="tab.dailyTimes.push('10:00')"
                  >
                    添加时间
                  </el-button>
                </div>
                <div class="schedule-item">
                  <span class="label">开始天数：</span>
                  <el-input-number v-model="tab.startDays" :min="0" :step="1" :precision="0" />
                  <span class="schedule-tip">0=现在，1=明天，2=后天...</span>
                </div>
              </div>
            </div>
          </div>

          <div v-if="false" class="publish-mode-section">
            <h3>浏览器模式</h3>
            <div class="publish-mode-controls">
              <el-radio-group v-model="tab.publishMode">
                <el-radio-button label="headless">无头发布</el-radio-button>
                <el-radio-button label="headed">有头发布</el-radio-button>
              </el-radio-group>
              <p v-if="tab.publishMode === 'headed'" class="publish-mode-tip">
                点击发布后，轮到哪个账号执行，就拉起哪个账号对应的浏览器窗口。
              </p>
            </div>
          </div>

          <!-- 操作按钮 -->
          <div v-if="false" class="action-buttons">
            <el-button size="small" @click="cancelPublish(tab)">取消</el-button>
            <el-button
              size="small"
              type="primary"
              @click="confirmPublish(tab)"
              :loading="tab.publishing || false"
            >
              {{ tab.publishing ? '发布中...' : '发布' }}
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="aiCopyWaitVisible" class="ai-copy-wait-overlay">
      <div class="ai-copy-wait-dialog" role="status" aria-live="polite">
        <svg class="pl" width="240" height="240" viewBox="0 0 240 240">
          <circle class="pl__ring pl__ring--a" cx="120" cy="120" r="105" fill="none" stroke="#000" stroke-width="20" stroke-dasharray="0 660" stroke-dashoffset="-330" stroke-linecap="round"></circle>
          <circle class="pl__ring pl__ring--b" cx="120" cy="120" r="35" fill="none" stroke="#000" stroke-width="20" stroke-dasharray="0 220" stroke-dashoffset="-110" stroke-linecap="round"></circle>
          <circle class="pl__ring pl__ring--c" cx="85" cy="120" r="70" fill="none" stroke="#000" stroke-width="20" stroke-dasharray="0 440" stroke-linecap="round"></circle>
          <circle class="pl__ring pl__ring--d" cx="155" cy="120" r="70" fill="none" stroke="#000" stroke-width="20" stroke-dasharray="0 440" stroke-linecap="round"></circle>
        </svg>
        <div class="ai-copy-wait-text">AI 正在生成发布文案标题。请稍等，不要关闭页面</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onBeforeUnmount, onMounted } from 'vue'
import { Upload, Plus, Close, Folder } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { accountApi } from '@/api/account'
import { aiPublishApi } from '@/api/aiPublish'
import { useAccountStore } from '@/stores/account'
import { useAppStore } from '@/stores/app'
import { usePublishTaskStore } from '@/stores/publishTask'
import { materialApi } from '@/api/material'
import {
  buildPublishAccountPayload,
  filterPublishAccountsByGroup,
  formatPublishAccountDisplayName,
  getAvailablePublishAccounts,
  getSelectedPublishAccounts,
  hasSelectedPlatformAccount,
} from '@/utils/publishAccountSelection'
import {
  ACCOUNT_GROUP_STORAGE_KEY,
  UNGROUPED_GROUP_ID,
  normalizeAccountGroupState,
} from '@/utils/accountGroups'
import { validatePublishTitles } from '@/utils/publishTitleMapping'
import {
  buildPublishWorks,
  hasUnsupportedWeixinNoteWork,
  isImageFilename,
  isVideoFilename,
  validatePublishContents,
} from '@/utils/publishWorkMapping'
import { http } from '@/utils/request'
import {
  loadStoredPublishDraftState,
  removeStoredPublishDraftState,
  saveStoredPublishDraftState,
} from '@/utils/publishDraftStorage'

// API base URL
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5409'

// Authorization headers
const authHeaders = computed(() => ({
  'Authorization': `Bearer ${localStorage.getItem('token') || ''}`
}))

// 当前激活的tab
const activeTab = ref('tab1')
const globalPublishMode = ref('headless')
const aiCopyWaitVisible = ref(false)

// tab计数器
let tabCounter = 1

// 获取应用状态管理
const appStore = useAppStore()
const publishTaskStore = usePublishTaskStore()

// 上传相关状态
const uploadOptionsVisible = ref(false)
const localUploadVisible = ref(false)
const uploadMethodVisible = ref(false)
const materialLibraryVisible = ref(false)
const currentUploadTab = ref(null)
const selectedMaterials = ref([])
const materials = computed(() => appStore.materials)
const uploadFilesInput = ref(null)
const folderUploadInput = ref(null)
const folderUploading = ref(false)

// 批量发布相关状态
const batchPublishing = ref(false)

// 账号相关状态
const accountDialogVisible = ref(false)
const tempSelectedAccounts = ref([])
const currentTab = ref(null)

// 获取账号状态管理
const accountStore = useAccountStore()

// 当前发布页直接显示全部账号，由账号所属平台决定最终发布平台
const availableAccounts = computed(() => getAvailablePublishAccounts(accountStore.accounts))
const accountSidebarPlatformFilter = ref('all')
const accountSidebarGroupFilter = ref('all')
const accountSidebarKeyword = ref('')
const accountSidebarPlatforms = computed(() => (
  [...new Set(availableAccounts.value.map((account) => account.platform).filter(Boolean))]
))
const readStoredPublishAccountGroupState = () => {
  if (typeof window === 'undefined') {
    return { groups: [], assignments: {} }
  }

  try {
    const raw = window.localStorage.getItem(ACCOUNT_GROUP_STORAGE_KEY)
    if (!raw) {
      return { groups: [], assignments: {} }
    }

    const parsed = JSON.parse(raw)
    return {
      groups: Array.isArray(parsed?.groups) ? parsed.groups : [],
      assignments: parsed?.assignments && typeof parsed.assignments === 'object' ? parsed.assignments : {},
    }
  } catch (error) {
    console.error('读取发布中心账号分组缓存失败:', error)
    return { groups: [], assignments: {} }
  }
}
const accountSidebarGroupState = ref({ groups: [], assignments: {} })
const accountSidebarGroups = computed(() => ([
  ...accountSidebarGroupState.value.groups,
  { id: UNGROUPED_GROUP_ID, name: '未分组' },
]))
const openingSidebarAccountIds = ref([])
const loggingSidebarAccountIds = ref([])
const publishAccountLoginDialogVisible = ref(false)
const publishAccountLoginTarget = ref(null)
const publishAccountLoginConfirming = ref(false)
const globalAiGenerating = computed(() => tabs.some((tab) => tab.aiGenerating))
const hasAIGeneratableTabs = computed(() => (
  tabs.some((tab) => Array.isArray(tab.fileList) && tab.fileList.length > 0)
))

const isSidebarAccountSelected = (tab, accountId) => {
  return Array.isArray(tab?.selectedAccounts) && tab.selectedAccounts.includes(accountId)
}

const getOtherTabSelectedAccountLabels = (currentTab, accountId) => {
  const normalizedAccountId = String(accountId)
  return tabs
    .filter((tab) => tab?.name !== currentTab?.name)
    .filter((tab) => (
      Array.isArray(tab?.selectedAccounts)
      && tab.selectedAccounts.some((selectedAccountId) => String(selectedAccountId) === normalizedAccountId)
    ))
    .map((tab) => tab.label || tab.name)
}

const isSidebarAccountSelectedInOtherTabs = (tab, accountId) => {
  return getOtherTabSelectedAccountLabels(tab, accountId).length > 0
}

const getSidebarAccountSortPriority = (tab, account) => {
  if (isSidebarAccountSelected(tab, account.id)) {
    return 2
  }
  if (isSidebarAccountSelectedInOtherTabs(tab, account.id)) {
    return 1
  }
  return 0
}

const toggleSidebarAccountSelection = (tab, accountId) => {
  if (!tab || !Array.isArray(tab.selectedAccounts)) {
    return
  }

  const selectedIndex = tab.selectedAccounts.indexOf(accountId)
  if (selectedIndex >= 0) {
    tab.selectedAccounts.splice(selectedIndex, 1)
    return
  }

  tab.selectedAccounts.push(accountId)
}

const syncPublishAccountGroupState = (accounts = accountStore.accounts) => {
  accountSidebarGroupState.value = normalizeAccountGroupState(
    readStoredPublishAccountGroupState(),
    accounts,
  )

  const validGroupIds = new Set([
    'all',
    UNGROUPED_GROUP_ID,
    ...accountSidebarGroupState.value.groups.map((group) => group.id),
  ])
  if (!validGroupIds.has(accountSidebarGroupFilter.value)) {
    accountSidebarGroupFilter.value = 'all'
  }
}

watch(
  () => accountStore.accounts,
  (accounts) => {
    syncPublishAccountGroupState(accounts)
  },
  { immediate: true, deep: true },
)

const filteredSidebarAccounts = (tab) => {
  const normalizedKeyword = accountSidebarKeyword.value.trim().toLowerCase()
  const groupedAccounts = filterPublishAccountsByGroup(
    availableAccounts.value,
    accountSidebarGroupState.value,
    accountSidebarGroupFilter.value,
  )

  return groupedAccounts
    .filter((account) => (
      accountSidebarPlatformFilter.value === 'all'
      || account.platform === accountSidebarPlatformFilter.value
    ))
    .filter((account) => {
      if (!normalizedKeyword) {
        return true
      }

      return [account.name, account.platform]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(normalizedKeyword))
    })
    .sort((left, right) => {
      const leftPriority = getSidebarAccountSortPriority(tab, left)
      const rightPriority = getSidebarAccountSortPriority(tab, right)
      const priorityDelta = Number(rightPriority) - Number(leftPriority)
      if (priorityDelta !== 0) {
        return priorityDelta
      }

      return String(left.name || '').localeCompare(String(right.name || ''), 'zh-CN')
    })
}

const getPublishAccountAvatar = (account) => {
  if (account?.avatarUrl) {
    return account.avatarUrl
  }

  const fallbackName = encodeURIComponent(String(account?.name || account?.platform || '账号'))
  return `https://ui-avatars.com/api/?name=${fallbackName}&background=EFF4FF&color=2563EB&size=96`
}

const syncPublishCenterAccounts = async () => {
  const res = await accountApi.getAccounts()
  if (res.code === 200 && Array.isArray(res.data)) {
    accountStore.setAccounts(res.data)
  }
}

const hydratePublishAccounts = async () => {
  if (Array.isArray(accountStore.accounts) && accountStore.accounts.length > 0) {
    return
  }

  try {
    await syncPublishCenterAccounts()
  } catch (error) {
    console.error('发布中心初始化账号列表失败:', error)
  }
}

// 话题相关状态
const topicDialogVisible = ref(false)
const STATUS_LABEL_NORMAL = '\u6b63\u5e38'
const SIDEBAR_ACCOUNT_ACTION_OPEN = '\u6253\u5f00'
const SIDEBAR_ACCOUNT_ACTION_LOGIN = '\u767b\u5f55'
const commonCancelText = '\u53d6\u6d88'
const publishAccountLoginDialogTitle = '\u8d26\u53f7\u767b\u5f55'
const publishAccountLoginDialogLeadPrefix = '\u8bf7\u5728\u5df2\u6253\u5f00\u7684\u6d4f\u89c8\u5668\u7a97\u53e3\u5b8c\u6210'
const publishAccountLoginDialogFallbackName = '\u5f53\u524d\u8d26\u53f7'
const publishAccountLoginDialogLeadSuffix = '\u7684\u767b\u5f55\u3002'
const publishAccountLoginDialogTip = '\u5b8c\u6210\u626b\u7801\u6216\u6388\u6743\u540e\uff0c\u70b9\u51fb\u4e0b\u65b9\u201c\u6211\u5df2\u5b8c\u6210\u767b\u5f55\u201d\uff0c\u7cfb\u7edf\u4f1a\u81ea\u52a8\u4fdd\u5b58 Cookie \u5e76\u5237\u65b0\u8fd9\u4e2a\u8d26\u53f7\u72b6\u6001\u3002'
const publishAccountLoginConfirmText = '\u6211\u5df2\u5b8c\u6210\u767b\u5f55'
const publishAccountLoginConfirmingText = '\u786e\u8ba4\u4e2d...'

const getSidebarAccountActionLabel = (account) => (
  account?.status === STATUS_LABEL_NORMAL ? SIDEBAR_ACCOUNT_ACTION_OPEN : SIDEBAR_ACCOUNT_ACTION_LOGIN
)

const isSidebarAccountActionLoading = (account) => {
  if (!account?.id) {
    return false
  }

  return openingSidebarAccountIds.value.includes(account.id) || loggingSidebarAccountIds.value.includes(account.id)
}

const closePublishAccountLoginDialog = () => {
  if (publishAccountLoginConfirming.value) {
    return
  }

  publishAccountLoginDialogVisible.value = false
  publishAccountLoginTarget.value = null
}

const openPublishCenterAccountBrowser = async (account) => {
  if (!account?.id || openingSidebarAccountIds.value.includes(account.id)) {
    return
  }

  openingSidebarAccountIds.value = [...openingSidebarAccountIds.value, account.id]
  try {
    const result = await accountApi.openAccountBrowser({ id: account.id })
    ElMessage.success(result.msg || `已打开 ${account.name} 的浏览器窗口`)
  } catch (error) {
    console.error('发布中心打开账号浏览器失败:', error)
    ElMessage.error(error?.message || '打开账号浏览器失败')
  } finally {
    openingSidebarAccountIds.value = openingSidebarAccountIds.value.filter((accountId) => accountId !== account.id)
  }
}

const startPublishCenterAccountLogin = async (account) => {
  if (!account?.id || loggingSidebarAccountIds.value.includes(account.id)) {
    return
  }

  loggingSidebarAccountIds.value = [...loggingSidebarAccountIds.value, account.id]
  try {
    const result = await accountApi.startBrowserLogin({
      type: String(account.type),
      id: account.name,
    })
    if (!result.data?.started) {
      throw new Error(result.msg || '账号登录启动失败')
    }

    publishAccountLoginTarget.value = account
    publishAccountLoginDialogVisible.value = true
    ElMessage.info(result.msg || '浏览器已打开，请完成扫码后点击确认')
  } catch (error) {
    console.error('发布中心启动账号登录失败:', error)
    ElMessage.error(error?.message || '启动登录失败')
  } finally {
    loggingSidebarAccountIds.value = loggingSidebarAccountIds.value.filter((accountId) => accountId !== account.id)
  }
}

const confirmPublishAccountLogin = async () => {
  if (!publishAccountLoginTarget.value) {
    return
  }

  publishAccountLoginConfirming.value = true
  try {
    const account = publishAccountLoginTarget.value
    const result = await accountApi.confirmBrowserLogin({
      type: String(account.type),
      id: account.name,
    })

    if (!result.data?.confirmed) {
      ElMessage.warning(result.msg || '尚未检测到登录成功，请完成扫码和授权后再试。')
      return
    }

    publishAccountLoginDialogVisible.value = false
    publishAccountLoginTarget.value = null
    await syncPublishCenterAccounts()
    ElMessage.success('账号 Cookie 已保存，状态已更新')
  } catch (error) {
    console.error('发布中心确认账号登录失败:', error)
    ElMessage.error(error?.message || '确认登录失败')
  } finally {
    publishAccountLoginConfirming.value = false
  }
}

const handleSidebarAccountAction = async (account) => {
  if (!account) {
    return
  }

  if (account.status === STATUS_LABEL_NORMAL) {
    await openPublishCenterAccountBrowser(account)
    return
  }

  await startPublishCenterAccountLogin(account)
}

const customTopic = ref('')

const RECOMMENDED_TOPICS_STORAGE_KEY = 'sau_publish_recommended_topics'
const DEFAULT_RECOMMENDED_TOPICS = [
  '游戏', '电影', '音乐', '美食', '旅行', '文化',
  '科技', '生活', '娱乐', '体育', '教育', '艺术',
  '健康', '时尚', '美妆', '摄影', '宠物', '汽车'
]

const normalizeTopicValue = (topic) => String(topic || '').trim().replace(/^#/, '')

const normalizeTopicList = (topics) => {
  if (!Array.isArray(topics)) {
    return []
  }

  return [...new Set(topics.map(normalizeTopicValue).filter(Boolean))]
}

const loadRecommendedTopics = () => {
  if (typeof window === 'undefined') {
    return [...DEFAULT_RECOMMENDED_TOPICS]
  }

  try {
    const raw = window.localStorage.getItem(RECOMMENDED_TOPICS_STORAGE_KEY)
    if (raw === null) {
      return [...DEFAULT_RECOMMENDED_TOPICS]
    }

    const parsed = JSON.parse(raw)
    return normalizeTopicList(parsed)
  } catch (error) {
    console.error('读取推荐话题失败:', error)
    return [...DEFAULT_RECOMMENDED_TOPICS]
  }
}

const recommendedTopics = ref(loadRecommendedTopics())

const saveRecommendedTopics = (topics) => {
  const normalizedTopics = normalizeTopicList(topics)
  recommendedTopics.value = normalizedTopics

  if (typeof window === 'undefined') {
    return
  }

  window.localStorage.setItem(
    RECOMMENDED_TOPICS_STORAGE_KEY,
    JSON.stringify(normalizedTopics)
  )
}

const DEFAULT_SELECTED_RECOMMENDED_TOPIC_COUNT = 5

const getDefaultSelectedTopics = (topics = recommendedTopics.value) => {
  return normalizeTopicList(topics).slice(0, DEFAULT_SELECTED_RECOMMENDED_TOPIC_COUNT)
}

const getPublishTabIdentity = (index) => ({
  name: `tab${index}`,
  label: `发布${index}`,
})

const createDefaultTabInit = () => ({
  name: 'tab1',
  label: '发布1',
  fileList: [], // 后端返回的文件名列表
  displayFileList: [], // 用于显示的文件列表
  selectedAccounts: [], // 选中的账号ID列表
  title: '',
  content: '',
  productLink: '', // 商品链接
  productTitle: '', // 商品名称
  selectedTopics: getDefaultSelectedTopics(),
  scheduleEnabled: false, // 定时发布开关
  videosPerDay: 1, // 每天发布视频数量
  dailyTimes: ['10:00'], // 每天发布时间点列表
  startDays: 0, // 开始天数，0表示现在，1表示明天，2表示后天
  publishMode: 'headless', // 发布浏览器模式，headless=无头，headed=有头
  publishStatus: null, // 发布状态，包含message和type
  publishing: false, // 发布状态，用于控制按钮loading效果
  aiGenerating: false, // AI 生成状态
  isDraft: false, // 是否保存为草稿，仅视频号平台可见
  isOriginal: false, // 是否标记为原创
  douyinSelfDeclaration: false, // 抖音自主声明，固定选择“内容由AI生成”
})

const makeNewTab = () => {
  const defaultTabInit = createDefaultTabInit()
  // prefer structuredClone when available (newer browsers/node), fallback to JSON
  try {
    return typeof structuredClone === 'function' ? structuredClone(defaultTabInit) : JSON.parse(JSON.stringify(defaultTabInit))
  } catch (e) {
    return JSON.parse(JSON.stringify(defaultTabInit))
  }
}

const clonePublishDraftFileList = (fileList) => {
  if (!Array.isArray(fileList)) {
    return []
  }

  return fileList
    .filter((item) => item && typeof item === 'object')
    .map((item) => JSON.parse(JSON.stringify(item)))
}

const normalizeDraftTimeList = (dailyTimes) => {
  if (!Array.isArray(dailyTimes) || dailyTimes.length === 0) {
    return ['10:00']
  }

  return dailyTimes
    .map((value) => String(value || '').trim())
    .filter(Boolean)
}

const buildDisplayFileList = (fileList) => [...fileList.map(item => ({
  name: item.name,
  url: item.url
}))]

const serializePublishDraftTab = (tab) => ({
  name: String(tab?.name || '').trim() || 'tab1',
  label: String(tab?.label || '').trim() || '发布1',
  fileList: clonePublishDraftFileList(tab?.fileList),
  selectedAccounts: Array.isArray(tab?.selectedAccounts) ? [...tab.selectedAccounts] : [],
  title: String(tab?.title || ''),
  content: String(tab?.content || ''),
  productLink: String(tab?.productLink || ''),
  productTitle: String(tab?.productTitle || ''),
  selectedTopics: normalizeTopicList(tab?.selectedTopics),
  scheduleEnabled: !!tab?.scheduleEnabled,
  videosPerDay: Number(tab?.videosPerDay) > 0 ? Number(tab.videosPerDay) : 1,
  dailyTimes: normalizeDraftTimeList(tab?.dailyTimes),
  startDays: Number.isFinite(Number(tab?.startDays)) ? Number(tab.startDays) : 0,
  isDraft: !!tab?.isDraft,
  isOriginal: !!tab?.isOriginal,
  douyinSelfDeclaration: !!tab?.douyinSelfDeclaration,
})

const restorePublishDraftTab = (rawTab, index) => {
  const defaultTab = makeNewTab()
  const tabIdentity = getPublishTabIdentity(index + 1)
  const normalizedTab = serializePublishDraftTab({
    ...defaultTab,
    ...rawTab,
    name: rawTab?.name || tabIdentity.name,
    label: rawTab?.label || tabIdentity.label,
  })

  return {
    ...defaultTab,
    ...normalizedTab,
    name: normalizedTab.name || tabIdentity.name,
    label: normalizedTab.label || tabIdentity.label,
    displayFileList: buildDisplayFileList(normalizedTab.fileList),
    publishStatus: null,
    publishing: false,
  }
}

const loadPublishDraftState = () => {
  const draftState = loadStoredPublishDraftState()
  if (!draftState || !Array.isArray(draftState.tabs) || draftState.tabs.length === 0) {
    return null
  }

  const restoredTabs = draftState.tabs.map((tab, index) => restorePublishDraftTab(tab, index))
  const restoredActiveTab = restoredTabs.some((tab) => tab.name === draftState.activeTab)
    ? draftState.activeTab
    : restoredTabs[0].name

  return {
    activeTab: restoredActiveTab,
    globalPublishMode: draftState.globalPublishMode === 'headed' ? 'headed' : 'headless',
    tabs: restoredTabs,
  }
}

const getPublishTabCounterSeed = (tabList) => {
  if (!Array.isArray(tabList) || tabList.length === 0) {
    return 1
  }

  return tabList.reduce((maxCounter, tab) => {
    const matched = String(tab?.name || '').match(/^tab(\d+)$/i)
    const currentCounter = matched ? Number(matched[1]) : 1
    return Number.isFinite(currentCounter) ? Math.max(maxCounter, currentCounter) : maxCounter
  }, 1)
}

// tab页数据 - 默认只有一个tab (use deep copy to avoid shared refs)
const publishDraftState = loadPublishDraftState()

const tabs = reactive(
  publishDraftState?.tabs?.length
    ? publishDraftState.tabs
    : [makeNewTab()]
)

activeTab.value = publishDraftState?.activeTab || tabs[0]?.name || 'tab1'
globalPublishMode.value = publishDraftState?.globalPublishMode === 'headed' ? 'headed' : 'headless'
tabCounter = getPublishTabCounterSeed(tabs)

let publishDraftSaveTimer = null

const savePublishDraftState = () => {
  saveStoredPublishDraftState({
    activeTab: activeTab.value,
    globalPublishMode: globalPublishMode.value,
    tabs: tabs.map(serializePublishDraftTab),
  })
}

const schedulePublishDraftSave = () => {
  if (typeof window === 'undefined') {
    return
  }

  if (publishDraftSaveTimer !== null) {
    window.clearTimeout(publishDraftSaveTimer)
  }

  publishDraftSaveTimer = window.setTimeout(() => {
    publishDraftSaveTimer = null
    savePublishDraftState()
  }, 250)
}

const resetTabToDraftDefault = (tab) => {
  const currentIdentity = {
    name: tab.name,
    label: tab.label,
  }
  const defaultTab = makeNewTab()

  tab.fileList = clonePublishDraftFileList(defaultTab.fileList)
  tab.displayFileList = buildDisplayFileList(tab.fileList)
  tab.selectedAccounts = [...defaultTab.selectedAccounts]
  tab.title = defaultTab.title
  tab.content = defaultTab.content
  tab.productLink = defaultTab.productLink
  tab.productTitle = defaultTab.productTitle
  tab.selectedTopics = [...defaultTab.selectedTopics]
  tab.scheduleEnabled = defaultTab.scheduleEnabled
  tab.videosPerDay = defaultTab.videosPerDay
  tab.dailyTimes = [...defaultTab.dailyTimes]
  tab.startDays = defaultTab.startDays
  tab.publishStatus = null
  tab.publishing = false
  tab.isDraft = defaultTab.isDraft
  tab.isOriginal = defaultTab.isOriginal
  tab.douyinSelfDeclaration = defaultTab.douyinSelfDeclaration
  tab.name = currentIdentity.name
  tab.label = currentIdentity.label
}

const clearAllPublishDrafts = ({ preserveOneTab = true } = {}) => {
  removeStoredPublishDraftState()
  globalPublishMode.value = 'headless'

  if (preserveOneTab) {
    tabs.splice(0, tabs.length, makeNewTab())
    tabCounter = tabs.length
    activeTab.value = tabs[0]?.name || 'tab1'
    return
  }

  tabs.splice(0, tabs.length)
  tabCounter = 0
  activeTab.value = 'tab1'
}

// 添加新tab
const toggleGlobalPublishMode = () => {
  globalPublishMode.value = globalPublishMode.value === 'headed' ? 'headless' : 'headed'
  ElMessage.success(globalPublishMode.value === 'headed' ? '当前为有头发布模式' : '当前为无头发布模式')
}

const addTab = () => {
  tabCounter++
  const newTab = makeNewTab()
  newTab.name = `tab${tabCounter}`
  newTab.label = `发布${tabCounter}`
  tabs.push(newTab)
  activeTab.value = newTab.name
}

// 删除tab
const removeTab = (tabName) => {
  const index = tabs.findIndex(tab => tab.name === tabName)
  if (index > -1) {
    tabs.splice(index, 1)
    // 如果删除的是当前激活的tab，切换到第一个tab
    if (activeTab.value === tabName && tabs.length > 0) {
      activeTab.value = tabs[0].name
    }
  }
}

// 处理文件上传成功
watch(tabs, () => {
  schedulePublishDraftSave()
}, { deep: true })

watch(activeTab, () => {
  schedulePublishDraftSave()
})

watch(globalPublishMode, () => {
  schedulePublishDraftSave()
})

onMounted(() => {
  hydratePublishAccounts()
})

onBeforeUnmount(() => {
  if (publishDraftSaveTimer !== null) {
    window.clearTimeout(publishDraftSaveTimer)
    publishDraftSaveTimer = null
  }
})

const refreshDisplayFileList = (tab) => {
  tab.displayFileList = buildDisplayFileList(tab.fileList)
}

const createUploadedFileInfo = ({ filePath, fileName, fileSize, fileType, entryKind = 'video', files = [] }) => {
  const filename = String(filePath).split('/').pop()
  return {
    name: fileName,
    url: entryKind === 'video' ? materialApi.getMaterialPreviewUrl(filename) : '',
    path: filePath,
    size: fileSize,
    type: fileType,
    entryKind,
    files,
  }
}

const handleUploadSuccess = (response, file, tab) => {
  if (response.code === 200) {
    // 获取文件路径
    const filePath = response.data.path || response.data
    // 从路径中提取文件名
    const filename = filePath.split('/').pop()
    const isImageWork = isImageFilename(file.name) && !isVideoFilename(file.name)
    
    // 保存文件信息到fileList，包含文件路径和其他信息
    const fileInfo = {
      name: file.name,
      url: materialApi.getMaterialPreviewUrl(filename), // 使用getMaterialPreviewUrl生成预览URL
      path: filePath,
      size: file.size,
      type: file.type,
      entryKind: isImageWork ? 'note' : 'video',
      files: isImageWork ? [{
        name: file.name,
        url: materialApi.getMaterialPreviewUrl(filename),
        path: filePath,
        size: file.size,
        type: file.type
      }] : []
    }
    
    // 添加到文件列表
    tab.fileList.push(fileInfo)
    
    // 更新显示列表
    tab.displayFileList = [...tab.fileList.map(item => ({
      name: item.name,
      url: item.url
    }))]
    
    ElMessage.success('文件上传成功')
  } else {
    ElMessage.error(response.msg || '上传失败')
  }
}

// 处理文件上传失败
const openUploadMethodPicker = () => {
  uploadMethodVisible.value = true
}

const triggerNativeFilePicker = (inputElement) => {
  if (!inputElement) {
    return
  }

  if (typeof inputElement.showPicker === 'function') {
    try {
      inputElement.showPicker()
      return
    } catch (error) {
      console.warn('showPicker failed, fallback to click:', error)
    }
  }

  inputElement.click()
}

const resolveInputRefElement = (inputRefValue) => {
  const candidates = Array.isArray(inputRefValue) ? inputRefValue : [inputRefValue]
  return candidates.find((candidate) => candidate?.tagName === 'INPUT') || null
}

const resetInputRefValue = (inputRefValue) => {
  const inputElement = resolveInputRefElement(inputRefValue)
  if (inputElement) {
    inputElement.value = ''
  }
  return inputElement
}

const openFileUploadPicker = () => {
  const inputElement = resetInputRefValue(uploadFilesInput.value)
  if (inputElement) {
    triggerNativeFilePicker(inputElement)
  }
  uploadMethodVisible.value = false
}

const normalizeFileSelectionEntry = (file) => {
  if (isVideoFilename(file.name)) {
    return {
      kind: 'video-file',
      name: file.name,
      file,
    }
  }

  if (isImageFilename(file.name)) {
    return {
      kind: 'image-file',
      name: file.name,
      file,
    }
  }

  throw new Error(`文件 ${file.name} 不是支持的图片或视频格式`)
}

const buildDirectoryEntries = (rawFiles) => {
  const entries = []
  const folderGroups = new Map()

  for (const file of Array.from(rawFiles || [])) {
    const relativePath = String(file.webkitRelativePath || file.name || '')
    const segments = relativePath.split('/').filter(Boolean)
    if (segments.length < 2) {
      continue
    }

    if (segments.length === 2) {
      entries.push(normalizeFileSelectionEntry(file))
      continue
    }

    const folderName = segments[1]
    if (!folderGroups.has(folderName)) {
      folderGroups.set(folderName, [])
    }
    folderGroups.get(folderName).push(file)
  }

  for (const [folderName, files] of folderGroups.entries()) {
    entries.push({
      kind: 'directory',
      name: folderName,
      files,
    })
  }

  return entries
}

const openFolderUploadPicker = async () => {
  if (typeof window !== 'undefined' && typeof window.showDirectoryPicker === 'function') {
    try {
      const directoryHandle = await window.showDirectoryPicker()
      const files = []
      for await (const entry of directoryHandle.values()) {
        if (entry.kind !== 'file') {
          throw new Error('图片文件夹里只能直接包含图片文件')
        }
        const file = await entry.getFile()
        Object.defineProperty(file, 'webkitRelativePath', {
          configurable: true,
          value: `${directoryHandle.name}/${file.name}`,
        })
        files.push(file)
      }

      await handleFolderUploadChange({
        target: {
          files,
        },
      })
      return
    } catch (error) {
      if (error?.name !== 'AbortError') {
        console.error('folder picker failed:', error)
        ElMessage.error(error.message || '图片文件夹读取失败')
      }
      return
    }
  }

  const inputElement = resetInputRefValue(folderUploadInput.value)
  if (inputElement) {
    triggerNativeFilePicker(inputElement)
  }
}

const readDirectoryHandleFiles = async (directoryHandle, prefix = directoryHandle.name) => {
  const files = []

  for await (const entry of directoryHandle.values()) {
    if (entry.kind === 'file') {
      const file = await entry.getFile()
      Object.defineProperty(file, 'webkitRelativePath', {
        configurable: true,
        value: `${prefix}/${file.name}`,
      })
      files.push(file)
      continue
    }

    if (entry.kind === 'directory') {
      const childFiles = await readDirectoryHandleFiles(entry, `${prefix}/${entry.name}`)
      files.push(...childFiles)
    }
  }

  return files
}

const openDirectoryUploadPicker = async () => {
  if (typeof window !== 'undefined' && typeof window.showDirectoryPicker === 'function') {
    try {
      const directoryHandle = await window.showDirectoryPicker()
      const files = await readDirectoryHandleFiles(directoryHandle)
      await handleDirectoryUploadChange({
        target: {
          files,
        },
      })
      uploadMethodVisible.value = false
      return
    } catch (error) {
      if (error?.name !== 'AbortError') {
        console.error('directory picker failed:', error)
        ElMessage.error(error.message || '目录读取失败')
      }
      return
    }
  }

  const inputElement = resetInputRefValue(folderUploadInput.value)
  if (inputElement) {
    triggerNativeFilePicker(inputElement)
  }
  uploadMethodVisible.value = false
}

const groupFolderFiles = (rawFiles) => {
  const groups = new Map()
  for (const file of Array.from(rawFiles || [])) {
    const relativePath = String(file.webkitRelativePath || file.name || '')
    const segments = relativePath.split('/').filter(Boolean)
    if (segments.length < 2) {
      continue
    }
    const folderName = segments[0]
    if (!groups.has(folderName)) {
      groups.set(folderName, [])
    }
    groups.get(folderName).push(file)
  }
  return Array.from(groups.entries()).map(([folderName, files]) => ({ folderName, files }))
}

const appendUploadEntries = async (entries) => {
  if (!currentUploadTab.value) {
    return
  }

  if (!Array.isArray(entries) || entries.length === 0) {
    ElMessage.warning('请至少选择一个文件或目录')
    return
  }

  folderUploading.value = true
  const addedWorks = []
  try {
    for (const entry of entries) {
      if (entry.kind === 'video-file') {
        const uploadedFile = await uploadSingleFile(entry.file)
        addedWorks.push(createUploadedFileInfo({
          filePath: uploadedFile.path,
          fileName: uploadedFile.name,
          fileSize: uploadedFile.size,
          fileType: uploadedFile.type,
          entryKind: 'video',
        }))
        continue
      }

      if (entry.kind === 'image-file') {
        const uploadedImage = await uploadSingleFile(entry.file)
        addedWorks.push({
          name: entry.name,
          url: '',
          path: `image:${Date.now()}:${entry.name}:${Math.random().toString(36).slice(2, 8)}`,
          size: Number(uploadedImage.size || 0),
          type: uploadedImage.type || 'image',
          entryKind: 'note',
          files: [uploadedImage],
        })
        continue
      }

      if (!entry.files.every((folderFile) => isImageFilename(folderFile.name))) {
        throw new Error(`目录 ${entry.name} 中只能包含图片文件`)
      }

      const uploadedFiles = await Promise.all(entry.files.map(uploadSingleFile))
      const totalSize = uploadedFiles.reduce((sum, item) => sum + Number(item.size || 0), 0)
      addedWorks.push({
        name: entry.name,
        url: '',
        path: `folder:${Date.now()}:${entry.name}:${Math.random().toString(36).slice(2, 8)}`,
        size: totalSize,
        type: 'directory',
        entryKind: 'note',
        files: uploadedFiles,
      })
    }

    currentUploadTab.value.fileList.push(...addedWorks)
    refreshDisplayFileList(currentUploadTab.value)
    localUploadVisible.value = false
    ElMessage.success(`已添加 ${addedWorks.length} 个作品`)
  } catch (error) {
    console.error('upload entries failed:', error)
    ElMessage.error(error.message || '素材导入失败')
  } finally {
    folderUploading.value = false
    resetInputRefValue(uploadFilesInput.value)
    resetInputRefValue(folderUploadInput.value)
  }
}

const uploadSingleFile = async (file) => {
  const formData = new FormData()
  formData.append('file', file)
  const response = await http.upload('/upload', formData)
  const filePath = response.data?.path || response.data
  const filename = String(filePath).split('/').pop()
  return {
    name: file.name,
    url: materialApi.getMaterialPreviewUrl(filename),
    path: filePath,
    size: file.size,
    type: file.type,
    relativePath: file.webkitRelativePath || file.name,
  }
}

const handleFileUploadChange = async (event) => {
  const files = Array.from(event.target.files || [])
  if (!files.length) {
    return
  }

  const entries = files.map(normalizeFileSelectionEntry)
  await appendUploadEntries(entries)
}

const handleDirectoryUploadChange = async (event) => {
  const entries = buildDirectoryEntries(event.target.files)
  await appendUploadEntries(entries)
}

const readDroppedEntryFiles = async (entry, parentPath = '') => {
  if (entry.isFile) {
    return await new Promise((resolve, reject) => {
      entry.file((file) => {
        const relativePath = parentPath ? `${parentPath}/${file.name}` : file.name
        Object.defineProperty(file, 'webkitRelativePath', {
          configurable: true,
          value: relativePath,
        })
        resolve([file])
      }, reject)
    })
  }

  if (!entry.isDirectory) {
    return []
  }

  const readAllEntries = async (reader) => {
    const collected = []
    while (true) {
      const chunk = await new Promise((resolve, reject) => reader.readEntries(resolve, reject))
      if (!chunk.length) {
        break
      }
      collected.push(...chunk)
    }
    return collected
  }

  const nextPath = parentPath ? `${parentPath}/${entry.name}` : entry.name
  const reader = entry.createReader()
  const childEntries = await readAllEntries(reader)
  const nestedFiles = await Promise.all(childEntries.map((child) => readDroppedEntryFiles(child, nextPath)))
  return nestedFiles.flat()
}

const handleCustomUploadDrop = async (event) => {
  const transferItems = Array.from(event.dataTransfer?.items || [])
  const transferFiles = Array.from(event.dataTransfer?.files || [])
  if (!transferItems.length && !transferFiles.length) {
    return
  }

  const droppedEntries = transferItems
    .map((item) => (typeof item.webkitGetAsEntry === 'function' ? item.webkitGetAsEntry() : null))
    .filter(Boolean)
  const hasDirectoryEntry = droppedEntries.some((entry) => entry.isDirectory)

  if (!hasDirectoryEntry && transferFiles.length) {
    await appendUploadEntries(transferFiles.map(normalizeFileSelectionEntry))
    return
  }

  const normalizedEntries = []

  for (const entry of droppedEntries) {
    if (entry.isDirectory) {
      const files = await readDroppedEntryFiles(entry)
      normalizedEntries.push({
        kind: 'directory',
        name: entry.name,
        files,
      })
      continue
    }

    const droppedFiles = await readDroppedEntryFiles(entry)
    if (droppedFiles[0]) {
      normalizedEntries.push(normalizeFileSelectionEntry(droppedFiles[0]))
    }
  }

  if (!normalizedEntries.length && transferFiles.length) {
    normalizedEntries.push(...transferFiles.map(normalizeFileSelectionEntry))
  }

  await appendUploadEntries(normalizedEntries)
}

const handleFolderUploadChange = async (event) => {
  if (!currentUploadTab.value) {
    return
  }

  const folderGroups = groupFolderFiles(event.target.files)
  if (folderGroups.length === 0) {
    ElMessage.warning('请选择至少一个图片文件夹')
    return
  }

  folderUploading.value = true
  const addedWorks = []
  try {
    for (const group of folderGroups) {
      if (!group.files.every((folderFile) => isImageFilename(folderFile.name))) {
        throw new Error(`文件夹 ${group.folderName} 里只能包含图片文件`)
      }

      const uploadedFiles = await Promise.all(group.files.map(uploadSingleFile))
      const totalSize = uploadedFiles.reduce((sum, item) => sum + Number(item.size || 0), 0)
      addedWorks.push({
        name: group.folderName,
        url: '',
        path: `folder:${Date.now()}:${group.folderName}:${Math.random().toString(36).slice(2, 8)}`,
        size: totalSize,
        type: 'directory',
        entryKind: 'note',
        files: uploadedFiles,
      })
    }

    currentUploadTab.value.fileList.push(...addedWorks)
    currentUploadTab.value.displayFileList = [...currentUploadTab.value.fileList.map(item => ({
      name: item.name,
      url: item.url
    }))]
    localUploadVisible.value = false
    ElMessage.success(`已添加 ${addedWorks.length} 个图文作品`)
  } catch (error) {
    console.error('folder upload failed:', error)
    ElMessage.error(error.message || '图片文件夹上传失败')
  } finally {
    folderUploading.value = false
    resetInputRefValue(folderUploadInput.value)
  }
}

const handleUploadError = (error) => {
  ElMessage.error('文件上传失败')
}

// 删除已上传文件
const removeFile = (tab, index) => {
  // 从文件列表中删除
  tab.fileList.splice(index, 1)
  
  // 更新显示列表
  tab.displayFileList = [...tab.fileList.map(item => ({
    name: item.name,
    url: item.url
  }))]
  
  ElMessage.success('文件删除成功')
}

// 话题相关方法
// 打开添加话题弹窗
const openTopicDialog = (tab) => {
  currentTab.value = tab
  topicDialogVisible.value = true
}

// 添加自定义话题
const addCustomTopic = () => {
  const topic = normalizeTopicValue(customTopic.value)

  if (!topic) {
    ElMessage.warning('请输入话题内容')
    return
  }

  let hasChange = false

  if (currentTab.value && !currentTab.value.selectedTopics.includes(topic)) {
    currentTab.value.selectedTopics.push(topic)
    hasChange = true
  }

  if (!recommendedTopics.value.includes(topic)) {
    saveRecommendedTopics([...recommendedTopics.value, topic])
    hasChange = true
  }

  customTopic.value = ''

  if (hasChange) {
    ElMessage.success('话题添加成功')
  } else {
    ElMessage.warning('话题已存在')
  }
}

// 切换推荐话题
const toggleRecommendedTopic = (topic) => {
  if (!currentTab.value) return
  
  const index = currentTab.value.selectedTopics.indexOf(topic)
  if (index > -1) {
    currentTab.value.selectedTopics.splice(index, 1)
  } else {
    currentTab.value.selectedTopics.push(topic)
  }
}

// 删除话题
const removeTopic = (tab, index) => {
  tab.selectedTopics.splice(index, 1)
}

const removeRecommendedTopicFromLibrary = (topic) => {
  saveRecommendedTopics(recommendedTopics.value.filter(item => item !== topic))
  ElMessage.success('推荐话题已删除')
}

// 确认添加话题
const confirmTopicSelection = () => {
  topicDialogVisible.value = false
  customTopic.value = ''
  currentTab.value = null
  ElMessage.success('添加话题完成')
}

// 账号选择相关方法
// 打开账号选择弹窗
const openAccountDialog = (tab) => {
  currentTab.value = tab
  tempSelectedAccounts.value = [...tab.selectedAccounts]
  accountDialogVisible.value = true
}

// 确认账号选择
const confirmAccountSelection = () => {
  if (currentTab.value) {
    currentTab.value.selectedAccounts = [...tempSelectedAccounts.value]
  }
  accountDialogVisible.value = false
  currentTab.value = null
  ElMessage.success('账号选择完成')
}

const tabHasSelectedPlatform = (tab, platformType) => {
  return hasSelectedPlatformAccount(accountStore.accounts, tab?.selectedAccounts || [], platformType)
}

// 删除选中的账号
const removeAccount = (tab, index) => {
  tab.selectedAccounts.splice(index, 1)
}

const generatePublishCopyForTab = async (tab) => {
  if (!tab || tab.aiGenerating) {
    return { skipped: true, reason: 'busy' }
  }

  if (!Array.isArray(tab.fileList) || tab.fileList.length === 0) {
    return { skipped: true, reason: 'empty' }
  }

  let works = []
  try {
    works = buildPublishWorks(tab.fileList)
  } catch (error) {
    throw new Error(error.message || '作品识别失败')
  }

  const selectedAccounts = getSelectedPublishAccounts(accountStore.accounts, tab.selectedAccounts)
  const platforms = [...new Set(selectedAccounts.map((account) => account.platform).filter(Boolean))]
  const accountNames = selectedAccounts.map((account) => account.name).filter(Boolean)

  tab.aiGenerating = true
  try {
    const response = await aiPublishApi.generatePublishCenterCopy({
      works: works.map((work) => ({
        kind: work.kind,
        name: work.name,
        filePaths: [...work.filePaths],
      })),
      platforms,
      accounts: accountNames,
    })

    const generated = response.data || {}
    tab.title = String(generated.titleText || '')
    tab.content = String(generated.contentText || '')
    return { skipped: false, tabName: tab.name, tabLabel: tab.label }
  } catch (error) {
    console.error('publish center ai generate failed:', error)
    throw new Error(error?.response?.data?.msg || error?.message || 'AI 生成失败')
  } finally {
    tab.aiGenerating = false
  }
}

const generatePublishCopy = async () => {
  const aiReadyTabs = tabs.filter((tab) => Array.isArray(tab.fileList) && tab.fileList.length > 0 && !tab.aiGenerating)

  if (aiReadyTabs.length === 0) {
    ElMessage.error('请先上传作品')
    return
  }

  aiCopyWaitVisible.value = true
  try {
    const results = await Promise.allSettled(
      tabs.map((tab) => generatePublishCopyForTab(tab))
    )

    const succeededTabs = []
    const failedTabs = []

    results.forEach((result, index) => {
      const tab = tabs[index]
      if (!tab) {
        return
      }

      if (result.status === 'fulfilled') {
        if (!result.value?.skipped) {
          succeededTabs.push(tab.label)
        }
        return
      }

      failedTabs.push({
        label: tab.label,
        message: result.reason?.message || 'AI 生成失败',
      })
    })

    if (succeededTabs.length > 0 && failedTabs.length === 0) {
      ElMessage.success(`AI 已生成 ${succeededTabs.length} 个 Tab 的标题和文案`)
      return
    }

    if (succeededTabs.length > 0 && failedTabs.length > 0) {
      ElMessage.warning(`已生成 ${succeededTabs.length} 个 Tab，失败 ${failedTabs.length} 个`)
      return
    }

    if (failedTabs.length > 0) {
      ElMessage.error(failedTabs[0].message || 'AI 生成失败')
    }
  } finally {
    aiCopyWaitVisible.value = false
  }
}

// 获取账号显示名称
const getAccountDisplayName = (accountId) => {
  const account = accountStore.accounts.find(acc => acc.id === accountId)
  return account ? formatPublishAccountDisplayName(account) : accountId
}

// 取消发布
const cancelPublish = (tab) => {
  ElMessage.info('已取消发布')
}

// 确认发布
const buildPublishPayloadForTab = (tab) => {
  if (tab.fileList.length === 0) {
    ElMessage.error('请先上传作品')
    throw new Error('请先上传作品')
  }

  let works = []
  try {
    works = buildPublishWorks(tab.fileList)
  } catch (error) {
    ElMessage.error(error.message || '作品识别失败')
    throw error
  }

  const { titles, error: titleError } = validatePublishTitles({
    rawTitle: tab.title,
    workCount: works.length,
  })
  if (titleError) {
    ElMessage.error(titleError)
    throw new Error(titleError)
  }

  const { contents, error: contentError } = validatePublishContents({
    rawContent: tab.content,
    workCount: works.length,
  })
  if (contentError) {
    ElMessage.error(contentError)
    throw new Error(contentError)
  }

  if (tab.selectedAccounts.length === 0) {
    ElMessage.error('\u8bf7\u9009\u62e9\u53d1\u5e03\u8d26\u53f7')
    throw new Error('\u8bf7\u9009\u62e9\u53d1\u5e03\u8d26\u53f7')
  }

  const selectedAccountRecords = getSelectedPublishAccounts(accountStore.accounts, tab.selectedAccounts)
  if (selectedAccountRecords.length === 0) {
    ElMessage.error('\u6240\u9009\u8d26\u53f7\u4e0d\u5b58\u5728\u6216\u5df2\u5931\u6548\uff0c\u8bf7\u91cd\u65b0\u9009\u62e9')
    throw new Error('\u6240\u9009\u8d26\u53f7\u4e0d\u5b58\u5728\u6216\u5df2\u5931\u6548\uff0c\u8bf7\u91cd\u65b0\u9009\u62e9')
  }

  if (hasUnsupportedWeixinNoteWork(selectedAccountRecords, works)) {
    ElMessage.error('视频号目前不支持图文发布，请取消视频号账号或移除图文作品')
    throw new Error('视频号目前不支持图文发布，请取消视频号账号或移除图文作品')
  }

  const accountPayload = buildPublishAccountPayload(accountStore.accounts, tab.selectedAccounts)
  return {
    title: titles[0] || '',
    titles,
    content: contents[0] || '',
    contents,
    works: works.map((work) => work.kind === 'video'
      ? { kind: 'video', filePath: work.filePaths[0] }
      : { kind: 'note', filePaths: [...work.filePaths] }),
    tags: tab.selectedTopics,
    fileList: tab.fileList.map(file => file.path),
    accountIds: accountPayload.accountIds,
    accountList: accountPayload.accountList,
    enableTimer: tab.scheduleEnabled ? 1 : 0,
    videosPerDay: tab.scheduleEnabled ? tab.videosPerDay || 1 : 1,
    dailyTimes: tab.scheduleEnabled ? tab.dailyTimes || ['10:00'] : ['10:00'],
    startDays: tab.scheduleEnabled ? tab.startDays || 0 : 0,
    headless: globalPublishMode.value !== 'headed',
    category: tab.isOriginal ? 1 : 0,
    douyinSelfDeclaration: tabHasSelectedPlatform(tab, 3) ? !!tab.douyinSelfDeclaration : false,
    productLink: tab.productLink.trim() || '',
    productTitle: tab.productTitle.trim() || '',
    isDraft: tab.isDraft,
  }
}

const confirmPublish = async (tab) => {
  if (tab.publishing) {
    ElMessage.warning('\u5f53\u524d\u4efb\u52a1\u6b63\u5728\u63d0\u4ea4\uff0c\u8bf7\u7a0d\u5019\u518d\u8bd5')
    return null
  }

  tab.publishing = true
  try {
    const publishData = buildPublishPayloadForTab(tab)
    const response = await http.post('/postVideo', publishData)
    const task = response.data || {}

    publishTaskStore.trackTask({
      taskId: task.taskId,
      label: tab.label,
      mode: 'single',
      draftTabNames: [tab.name],
    })

    tab.publishStatus = {
      message: '\u4efb\u52a1\u5df2\u521b\u5efa\uff0c\u53ef\u524d\u5f80\u4efb\u52a1\u8fdb\u5ea6\u67e5\u770b\u65e5\u5fd7',
      type: 'info',
    }
    ElMessage.success('\u53d1\u5e03\u4efb\u52a1\u5df2\u521b\u5efa\uff0c\u53ef\u524d\u5f80\u4efb\u52a1\u8fdb\u5ea6\u67e5\u770b\u65e5\u5fd7')
    return task
  } catch (error) {
    console.error('publish submit failed:', error)
    tab.publishStatus = {
      message: `\u53d1\u5e03\u5931\u8d25\uff1a${error.message || '\u8bf7\u68c0\u67e5\u7f51\u7edc\u8fde\u63a5'}`,
      type: 'error',
    }
    return null
  } finally {
    tab.publishing = false
  }
}

const showUploadOptions = (tab) => {
  currentUploadTab.value = tab
  uploadOptionsVisible.value = true
}

const findDuplicateBatchAccounts = () => {
  const accountUsage = new Map()

  tabs.forEach((tab) => {
    const uniqueAccountIds = [...new Set((tab.selectedAccounts || []).map((accountId) => String(accountId)))]
    uniqueAccountIds.forEach((accountId) => {
      if (!accountUsage.has(accountId)) {
        accountUsage.set(accountId, [])
      }
      accountUsage.get(accountId).push(tab.label)
    })
  })

  const duplicateEntries = [...accountUsage.entries()]
    .filter(([, tabLabels]) => tabLabels.length > 1)
    .map(([accountId, tabLabels]) => {
      const account = accountStore.accounts.find((item) => String(item.id) === accountId)
      const accountName = account?.name || account?.userName || accountId
      return `${accountName}（${tabLabels.join('、')}）`
    })

  if (!duplicateEntries.length) {
    return null
  }

  return {
    entries: duplicateEntries,
    message: `同一个账号不能出现在多个 Tab 里：${duplicateEntries.join('；')}`,
  }
}

// 选择本地上传
const selectLocalUpload = () => {
  uploadOptionsVisible.value = false
  localUploadVisible.value = true
}

// 选择素材库
const selectMaterialLibrary = async () => {
  uploadOptionsVisible.value = false
  
  // 如果素材库为空，先获取素材数据
  if (materials.value.length === 0) {
    try {
      const response = await materialApi.getAllMaterials()
      if (response.code === 200) {
        appStore.setMaterials(response.data)
      } else {
        ElMessage.error('获取素材列表失败')
        return
      }
    } catch (error) {
      console.error('获取素材列表出错:', error)
      ElMessage.error('获取素材列表失败')
      return
    }
  }
  
  selectedMaterials.value = []
  materialLibraryVisible.value = true
}

// 确认素材选择
const confirmMaterialSelection = () => {
  if (selectedMaterials.value.length === 0) {
    ElMessage.warning('请选择至少一个素材')
    return
  }
  
  if (currentUploadTab.value) {
    // 将选中的素材添加到当前tab的文件列表
    selectedMaterials.value.forEach(materialId => {
      const material = materials.value.find(m => m.id === materialId)
      if (material) {
        const fileInfo = {
          name: material.filename,
          url: materialApi.getMaterialPreviewUrl(material.file_path.split('/').pop()),
          path: material.file_path,
          size: material.filesize * 1024 * 1024, // 转换为字节
          type: 'video/mp4'
        }
        
        // 检查是否已存在相同文件
        const exists = currentUploadTab.value.fileList.some(file => file.path === fileInfo.path)
        if (!exists) {
          currentUploadTab.value.fileList.push(fileInfo)
        }
      }
    })
    
    // 更新显示列表
    currentUploadTab.value.displayFileList = [...currentUploadTab.value.fileList.map(item => ({
      name: item.name,
      url: item.url
    }))]
  }
  
  const addedCount = selectedMaterials.value.length
  materialLibraryVisible.value = false
  selectedMaterials.value = []
  currentUploadTab.value = null
  ElMessage.success(`已添加 ${addedCount} 个素材`)
}

// 批量发布对话框状态
const batchPublish = async () => {
  if (batchPublishing.value) return

  const duplicateBatchAccounts = findDuplicateBatchAccounts()
  if (duplicateBatchAccounts) {
    ElMessage.error(duplicateBatchAccounts.message)
    return
  }

  batchPublishing.value = true
  try {
    const payloads = tabs.map(tab => buildPublishPayloadForTab(tab))
    const response = await http.post('/postVideoBatch', payloads)
    const task = response.data || {}

    publishTaskStore.trackTask({
      taskId: task.taskId,
      label: '\u6279\u91cf\u53d1\u5e03\uff08' + tabs.length + '\u4e2aTab\uff09',
      mode: 'batch',
      draftTabNames: tabs.map(tab => tab.name),
    })

    tabs.forEach(tab => {
      tab.publishStatus = {
        message: '\u4efb\u52a1\u5df2\u521b\u5efa\uff0c\u53ef\u524d\u5f80\u4efb\u52a1\u8fdb\u5ea6\u67e5\u770b\u65e5\u5fd7',
        type: 'info',
      }
    })

    ElMessage.success('\u6279\u91cf\u53d1\u5e03\u4efb\u52a1\u5df2\u521b\u5efa\uff0c\u53ef\u524d\u5f80\u4efb\u52a1\u8fdb\u5ea6\u67e5\u770b\u65e5\u5fd7')
  } catch (error) {
    console.error('batch publish submit failed:', error)
    ElMessage.error(error.message || '\u6279\u91cf\u53d1\u5e03\u51fa\u9519\uff0c\u8bf7\u91cd\u8bd5')
  } finally {
    batchPublishing.value = false
  }
}

</script>

<style lang="scss" scoped>
@use '@/styles/variables.scss' as *;

.ai-copy-wait-overlay {
  position: fixed;
  inset: 0;
  z-index: 3000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(15, 23, 42, 0.24);
  backdrop-filter: blur(6px);
}

.ai-copy-wait-dialog {
  width: min(420px, calc(100vw - 48px));
  min-height: 240px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 22px;
  padding: 36px 34px;
  border-radius: 24px;
  background: #fff;
  box-shadow: 0 24px 70px rgba(15, 23, 42, 0.22);
  text-align: center;
}

.ai-copy-wait-text {
  max-width: 320px;
  font-size: 16px;
  font-weight: 600;
  line-height: 1.7;
  color: #111827;
}

.pl {
  width: 6em;
  height: 6em;
}

.pl__ring {
  animation: ringA 2s linear infinite;
}

.pl__ring--a {
  stroke: #f42f25;
}

.pl__ring--b {
  animation-name: ringB;
  stroke: #f49725;
}

.pl__ring--c {
  animation-name: ringC;
  stroke: #255ff4;
}

.pl__ring--d {
  animation-name: ringD;
  stroke: #f42582;
}

@keyframes ringA {
  from, 4% {
    stroke-dasharray: 0 660;
    stroke-width: 20;
    stroke-dashoffset: -330;
  }

  12% {
    stroke-dasharray: 60 600;
    stroke-width: 30;
    stroke-dashoffset: -335;
  }

  32% {
    stroke-dasharray: 60 600;
    stroke-width: 30;
    stroke-dashoffset: -595;
  }

  40%, 54% {
    stroke-dasharray: 0 660;
    stroke-width: 20;
    stroke-dashoffset: -660;
  }

  62% {
    stroke-dasharray: 60 600;
    stroke-width: 30;
    stroke-dashoffset: -665;
  }

  82% {
    stroke-dasharray: 60 600;
    stroke-width: 30;
    stroke-dashoffset: -925;
  }

  90%, to {
    stroke-dasharray: 0 660;
    stroke-width: 20;
    stroke-dashoffset: -990;
  }
}

@keyframes ringB {
  from, 12% {
    stroke-dasharray: 0 220;
    stroke-width: 20;
    stroke-dashoffset: -110;
  }

  20% {
    stroke-dasharray: 20 200;
    stroke-width: 30;
    stroke-dashoffset: -115;
  }

  40% {
    stroke-dasharray: 20 200;
    stroke-width: 30;
    stroke-dashoffset: -195;
  }

  48%, 62% {
    stroke-dasharray: 0 220;
    stroke-width: 20;
    stroke-dashoffset: -220;
  }

  70% {
    stroke-dasharray: 20 200;
    stroke-width: 30;
    stroke-dashoffset: -225;
  }

  90% {
    stroke-dasharray: 20 200;
    stroke-width: 30;
    stroke-dashoffset: -305;
  }

  98%, to {
    stroke-dasharray: 0 220;
    stroke-width: 20;
    stroke-dashoffset: -330;
  }
}

@keyframes ringC {
  from {
    stroke-dasharray: 0 440;
    stroke-width: 20;
    stroke-dashoffset: 0;
  }

  8% {
    stroke-dasharray: 40 400;
    stroke-width: 30;
    stroke-dashoffset: -5;
  }

  28% {
    stroke-dasharray: 40 400;
    stroke-width: 30;
    stroke-dashoffset: -175;
  }

  36%, 58% {
    stroke-dasharray: 0 440;
    stroke-width: 20;
    stroke-dashoffset: -220;
  }

  66% {
    stroke-dasharray: 40 400;
    stroke-width: 30;
    stroke-dashoffset: -225;
  }

  86% {
    stroke-dasharray: 40 400;
    stroke-width: 30;
    stroke-dashoffset: -395;
  }

  94%, to {
    stroke-dasharray: 0 440;
    stroke-width: 20;
    stroke-dashoffset: -440;
  }
}

@keyframes ringD {
  from, 8% {
    stroke-dasharray: 0 440;
    stroke-width: 20;
    stroke-dashoffset: 0;
  }

  16% {
    stroke-dasharray: 40 400;
    stroke-width: 30;
    stroke-dashoffset: -5;
  }

  36% {
    stroke-dasharray: 40 400;
    stroke-width: 30;
    stroke-dashoffset: -175;
  }

  44%, 50% {
    stroke-dasharray: 0 440;
    stroke-width: 20;
    stroke-dashoffset: -220;
  }

  58% {
    stroke-dasharray: 40 400;
    stroke-width: 30;
    stroke-dashoffset: -225;
  }

  78% {
    stroke-dasharray: 40 400;
    stroke-width: 30;
    stroke-dashoffset: -395;
  }

  86%, to {
    stroke-dasharray: 0 440;
    stroke-width: 20;
    stroke-dashoffset: -440;
  }
}

.publish-center {
  display: flex;
  flex-direction: column;
  min-height: calc(100vh - 48px);
  gap: 18px;
  width: 100%;

  .publish-header {
    margin-bottom: 0 !important;
  }
  
  // Tab管理区域
  .tab-management {
    margin-bottom: 0;
    padding: 18px;
    
    .tab-header {
      display: flex;
      align-items: center;
      gap: 18px;
      
      .tab-list {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        flex: 1;
        min-width: 0;
        
        .tab-item {
           display: flex;
           align-items: center;
           gap: 6px;
           padding: 0 14px;
           background-color: #fff;
           border: 1px solid #d7deea;
           border-radius: 8px;
           cursor: pointer;
           transition: all 0.3s;
           font-size: 13px;
           height: 36px;
           
           &:hover {
             background-color: #f8fafd;
             border-color: #d5e0ff;
           }
           
           &.active {
             background-color: #3b63f6;
             border-color: #3b63f6;
             color: #fff;
             
             .close-icon {
               color: #fff;
               
               &:hover {
                 background-color: rgba(255, 255, 255, 0.2);
               }
             }
           }
           
           .close-icon {
             padding: 2px;
             border-radius: 2px;
             cursor: pointer;
             transition: background-color 0.3s;
             font-size: 12px;
             
             &:hover {
               background-color: rgba(0, 0, 0, 0.1);
             }
           }
         }
       }
       
      .tab-actions {
        display: flex;
        align-items: center;
        gap: 10px;
        flex-shrink: 0;
        
        .global-publish-mode-btn,
        .clear-draft-btn,
        .add-tab-btn,
        .global-ai-generate-btn,
        .batch-publish-btn {
          display: flex;
          align-items: center;
          gap: 4px;
          height: 36px;
          padding: 0 14px;
          font-size: 13px;
          white-space: nowrap;
        }
      }
    }
  }
  
  // 批量发布进度对话框样式
  .publish-progress {
    padding: 20px;
    
    .current-publishing {
      margin: 15px 0;
      text-align: center;
      color: #606266;
    }

    .publish-results {
      margin-top: 20px;
      border-top: 1px solid #EBEEF5;
      padding-top: 15px;
      max-height: 300px;
      overflow-y: auto;

      .result-item {
        display: flex;
        align-items: center;
        padding: 8px 0;
        color: #606266;

        .el-icon {
          margin-right: 8px;
        }

        .label {
          margin-right: 10px;
          font-weight: 500;
        }

        .message {
          color: #909399;
        }

        &.success {
          color: #67C23A;
        }

        &.error {
          color: #F56C6C;
        }

        &.cancelled {
          color: #909399;
        }
      }
    }
  }

  .dialog-footer {
    text-align: right;
  }
  
  // 内容区域
  .publish-content {
    flex: 1;
    background: transparent;
    border: 0;
    box-shadow: none;
    padding: 0;
    
    .tab-content-wrapper {
      display: flex;
      justify-content: center;
      
      .tab-content {
        width: 100%;
        max-width: 800px;
        
        h3 {
          font-size: 16px;
          font-weight: 500;
          color: $text-primary;
          margin: 0 0 10px 0;
        }
        
        .upload-section,
        .account-section,
        .title-section,
        .content-section,
        .product-section,
        .topic-section,
        .schedule-section {
          margin-bottom: 30px;
        }

        .account-section {
          .selected-accounts {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            min-height: 32px;
          }
        }

        .product-section {
          .product-name-input,
          .product-link-input {
            margin-bottom: 5px;
          }
        }
        
        .video-upload {
          width: 100%;
          position: relative;
          
          :deep(.el-upload-dragger) {
            width: 100%;
            height: 180px;
          }

          :deep(.el-upload__input) {
            display: none !important;
          }

          .custom-upload-directory-entry {
            position: relative;
            z-index: 3;
            margin-top: 10px;
            text-align: center;

            .directory-entry-btn {
              border: none;
              background: transparent;
              color: #409eff;
              font-size: 13px;
              cursor: pointer;
              padding: 0;
            }
          }

          .custom-upload-overlay {
            position: absolute;
            inset: 0;
            z-index: 2;
            cursor: pointer;
          }
        }
        
        .account-input {
          max-width: 400px;
        }
        
        .platform-buttons {
          display: flex;
          gap: 10px;
          flex-wrap: wrap;
          
          .platform-btn {
            min-width: 80px;
          }
        }
        
        .title-input {
          max-width: 600px;
        }
        
        .topic-display {
          display: flex;
          flex-direction: column;
          gap: 12px;
          
          .selected-topics {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            min-height: 32px;
            
            .topic-tag {
              font-size: 14px;
            }
          }
          
          .select-topic-btn {
            align-self: flex-start;
          }
        }
        
        .schedule-controls {
          display: flex;
          flex-direction: column;
          gap: 15px;

          .schedule-settings {
            margin-top: 15px;
            padding: 15px;
            background-color: #f5f7fa;
            border-radius: 4px;

            .schedule-item {
              display: flex;
              align-items: center;
              margin-bottom: 15px;

              &:last-child {
                margin-bottom: 0;
              }

              .label {
                min-width: 120px;
                margin-right: 10px;
              }

              .el-time-select {
                margin-right: 10px;
              }

              .schedule-tip {
                margin-left: 10px;
                color: #909399;
                font-size: 13px;
              }

              .el-button {
                margin-left: 10px;
              }
            }
          }
        }
        
        .action-buttons {
          display: flex;
          justify-content: flex-end;
          gap: 10px;
          margin-top: 30px;
          padding-top: 20px;
          border-top: 1px solid #ebeef5;
        }

        .draft-section {
          margin: 20px 0;

          .draft-checkbox {
            display: block;
            margin: 10px 0;
          }
        }

        .original-section {
          margin: 10px 0 20px;

        .original-checkbox {
            display: inline-flex;
            margin: 10px 16px 10px 0;
          }
        }
      }
    }
  }

  // 已上传文件列表样式
  .uploaded-files {
    margin-top: 20px;
    
    h4 {
      font-size: 16px;
      font-weight: 500;
      margin-bottom: 12px;
      color: #303133;
    }
    
    .file-list {
      display: flex;
      flex-direction: column;
      gap: 10px;
      
      .file-item {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 10px 15px;
        background-color: #f5f7fa;
        border-radius: 4px;
        
        .el-link {
          margin-right: 10px;
          max-width: 300px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .file-name,
        .file-detail {
          color: #606266;
          font-size: 13px;
        }
        
        .file-size {
          color: #909399;
          font-size: 13px;
          margin-right: auto;
      }
    }
  }

  .upload-method-actions {
    display: flex;
    justify-content: center;
    gap: 16px;
    padding: 8px 0;
  }
}

:deep(.local-upload-dialog .folder-upload-actions) {
  height: 0 !important;
  margin: 0 !important;
  overflow: visible !important;
}

:deep(.local-upload-dialog .folder-upload-actions > .el-button),
:deep(.local-upload-dialog .folder-upload-actions > .folder-upload-tip) {
  display: none !important;
}

:deep(.local-upload-dialog .folder-upload-input) {
  position: fixed !important;
  left: -9999px !important;
  top: -9999px !important;
  width: 1px !important;
  height: 1px !important;
  opacity: 0 !important;
  pointer-events: none !important;
}

  .account-dialog {
    .account-dialog-content {
      .account-list {
        display: flex;
        flex-direction: column;
        gap: 12px;
      }

      .account-item {
        margin-right: 0;
      }

      .account-info {
        display: flex;
        align-items: center;
        gap: 10px;
      }

      .account-platform {
        color: #909399;
        font-size: 13px;
      }
    }
  }
  
  // 添加话题弹窗样式
  .topic-dialog {
    .topic-dialog-content {
      .custom-topic-input {
        display: flex;
        gap: 12px;
        margin-bottom: 24px;
        
        .custom-input {
          flex: 1;
        }
      }
      
      .recommended-topics {
        h4 {
          margin: 0 0 16px 0;
          font-size: 16px;
          font-weight: 500;
          color: #303133;
        }
        
        .topic-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
          gap: 12px;

          .topic-item {
            display: flex;
            align-items: center;
            gap: 8px;

            .topic-btn {
              flex: 1;
              height: 36px;
              font-size: 14px;
              border-radius: 6px;
              min-width: 0;
              padding: 0 12px;
              white-space: nowrap;
              text-align: center;
              display: flex;
              align-items: center;
              justify-content: center;

              &.el-button--primary {
                background-color: #409eff;
                border-color: #409eff;
                color: white;
              }
            }

            .delete-topic-btn {
              width: 36px;
              height: 36px;
              padding: 0;
              color: #909399;

              &:hover {
                color: #f56c6c;
                border-color: #fbc4c4;
                background-color: #fef0f0;
              }
            }
          }
        }
      }
    }
    
    .dialog-footer {
      display: flex;
      justify-content: flex-end;
      gap: 12px;
    }
  }

  .publish-content {
    padding: 0;

    .tab-content-wrapper {
      justify-content: stretch;

      .tab-content {
        max-width: none;
      }
    }
  }

  .publish-workspace {
    display: grid;
    grid-template-columns: 274px minmax(420px, 680px) minmax(436px, 1fr);
    gap: 24px;
    align-items: stretch;
  }

  .account-sidebar,
  .upload-stage-panel,
  .content-config-panel {
    background: #fff;
    border: 1px solid #e3e8f0;
    border-radius: 14px;
    box-shadow: 0 8px 20px rgba(21, 32, 51, 0.05);
    min-width: 0;
    height: calc(100vh - 142px);
  }

  .account-sidebar,
  .content-config-panel {
    padding: 14px;
  }

  .sidebar-panel-header,
  .panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 0;

    h3 {
      margin: 0;
      font-size: 17px;
      font-weight: 600;
      line-height: 1.2;
      color: #1f2937;
    }

  }

  .account-sidebar {
    display: flex;
    flex-direction: column;
    gap: 8px;

    .sidebar-panel-header > div {
      width: 100%;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      min-height: 32px;
    }

    .sidebar-panel-header p {
      margin: 0;
      font-size: 12px;
      line-height: 1;
      color: #4f46e5;
      background: #eef2ff;
      border: 1px solid #dbeafe;
      border-radius: 999px;
      padding: 6px 10px;
      white-space: nowrap;
    }

    .account-sidebar-filters {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .account-sidebar-search-row {
      width: 100%;
    }

    .account-sidebar-select-row {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
      align-items: center;
    }

    .account-sidebar-list {
      display: flex;
      flex-direction: column;
      gap: 8px;
      flex: 1;
      min-height: 0;
      height: 100%;
      max-height: none;
      overflow-y: auto;
      padding-right: 2px;
    }

    .account-sidebar-item {
      display: grid;
      grid-template-columns: 36px minmax(0, 1fr) auto 18px;
      align-items: center;
      column-gap: 10px;
      padding: 9px 12px;
      border: 1px solid #e3e8f0;
      border-radius: 8px;
      background: #f8fafd;
      cursor: pointer;
      transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;

      &:hover {
        border-color: #d5e0ff;
        box-shadow: 0 8px 20px rgba(59, 99, 246, 0.08);
        transform: translateY(-1px);
      }

      &.selected {
        border-color: #3b63f6;
        background: #eef3ff;
      }

      &.selected-in-other-tab:not(.selected) {
        border-color: #f59e0b;
        background: #fffbeb;
      }
    }

    .account-sidebar-check {
      justify-self: end;
    }

    .account-sidebar-item :deep(.el-checkbox) {
      margin-right: 0;
      display: flex;
      align-items: center;
    }

    .account-sidebar-item.selected-in-other-tab:not(.selected) :deep(.el-checkbox__input.is-checked .el-checkbox__inner) {
      background-color: #f59e0b;
      border-color: #f59e0b;
    }

    .account-sidebar-item.selected-in-other-tab:not(.selected) :deep(.el-checkbox__input.is-checked + .el-checkbox__label) {
      color: #b45309;
    }

    .account-sidebar-avatar {
      width: 36px;
      height: 36px;
      flex-shrink: 0;
      background: #eff6ff;
      color: #2563eb;
      font-weight: 600;
    }

    .account-sidebar-meta {
      min-width: 0;
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .account-sidebar-name {
      min-width: 0;
      font-size: 14px;
      font-weight: 600;
      color: #111827;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .account-sidebar-actions {
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: 4px;
      min-width: 48px;
    }

    .account-sidebar-platform-tag {
      flex-shrink: 0;
      height: 22px;
      min-width: 48px;
      padding: 0 6px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }

    .other-tab-selected-tag {
      height: 22px;
      color: #b45309;
      border-color: #fbbf24;
      background: #fffbeb;
    }

    .account-sidebar-action-btn {
      margin: 0;
      padding: 0;
      min-height: auto;
      height: auto;
      font-size: 12px;
      line-height: 1;
    }

    .account-sidebar-status {
      font-size: 11px;
      color: #6b7280;
      line-height: 1.2;

      &.invalid {
        color: #dc2626;
      }
    }
  }

  .account-login-dialog {
    .account-login-dialog-content {
      display: flex;
      flex-direction: column;
      gap: 10px;
    }

    .account-login-dialog-title,
    .account-login-dialog-tip {
      margin: 0;
      line-height: 1.7;
      color: #4b5563;
    }

    .account-login-dialog-title {
      font-size: 14px;
      color: #1f2937;

      span {
        font-weight: 600;
        color: #111827;
      }
    }

    .account-login-dialog-tip {
      font-size: 13px;
    }
  }

  .upload-stage-panel {
    display: flex;
    flex-direction: column;
    min-height: 0;
    padding: 14px;

    .upload-section--panel {
      flex: 1;
      min-height: 0;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      border: 1px dashed #d7deea;
      border-radius: 12px;
      background: #fff;
      padding: 18px;

      &.is-empty {
        min-height: 300px;
      }

      &.is-empty .upload-stage-body {
        justify-content: center;
      }
    }

    .panel-header p {
      margin: 4px 0 0;
      font-size: 13px;
      line-height: 1.6;
      color: #6b7280;
    }

    .upload-stage-body {
      flex: 1;
      height: auto;
      min-height: 0;
      display: flex;
      flex-direction: column;
      gap: 12px;
      overflow: hidden;
    }

    .upload-options {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 10px;
      text-align: center;
      min-height: 128px;
      flex: 0 0 auto;
    }

    .upload-btn {
      min-width: 136px;
      height: 40px;
      border-radius: 999px;
      font-size: 15px;
    }

    .upload-stage-tip {
      margin: 0;
      max-width: 420px;
      font-size: 13px;
      line-height: 1.7;
      color: #6b7280;
    }

    .uploaded-files {
      flex: 1 1 auto;
      min-height: 0;
      display: flex;
      flex-direction: column;
      overflow: hidden;

      .file-list {
        flex: 1 1 auto;
        min-height: 0;
        max-height: none;
        overflow-y: auto;
        padding-right: 4px;
      }
    }
  }

  .content-config-panel {
    .content-config-scroll {
      display: flex;
      flex-direction: column;
      gap: 16px;
      height: 100%;
      max-height: none;
      overflow-y: auto;
      padding-right: 2px;
    }

    .content-config-toolbar {
      display: flex;
      justify-content: flex-end;
    }

    .ai-generate-btn {
      min-width: 88px;
      border-radius: 999px;
    }

    .product-section,
    .title-section,
    .content-section,
    .topic-section,
    .schedule-section {
      margin-bottom: 0;
    }

    .title-input,
    .content-input {
      max-width: none;
    }

    .schedule-controls {
      gap: 12px;
    }

    .schedule-settings {
      margin-top: 0;
    }

    .action-buttons {
      margin-top: auto;
      padding-top: 14px;
      border-top: 1px solid #eef2f7;
    }
  }

  .uploaded-files {
    margin-top: 0;

    h4 {
      margin-bottom: 12px;
      font-size: 14px;
      color: #1f2937;
    }

    .file-item {
      flex-wrap: wrap;
      border-radius: 12px;
      padding: 10px 12px;

      .el-link,
      .file-name {
        flex: 1 1 180px;
        min-width: 0;
      }
    }
  }

  @media (max-width: 1180px) {
    max-width: none;

    .publish-workspace {
      grid-template-columns: 274px minmax(340px, 1fr);
      gap: 12px;
    }

    .content-config-panel {
      grid-column: 1 / -1;
    }
  }

  @media (max-width: 1120px) {
    .publish-workspace {
      grid-template-columns: 1fr;
    }

    .account-sidebar,
    .upload-stage-panel,
    .content-config-panel {
      height: auto;
      min-height: auto;
    }

    .account-sidebar .account-sidebar-list,
    .content-config-panel .content-config-scroll {
      max-height: none;
      overflow: visible;
    }

    .upload-stage-panel .upload-section--panel {
      min-height: 420px;
      height: auto;
    }
  }
}
</style>

