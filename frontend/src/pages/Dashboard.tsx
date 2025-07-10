import React from 'react'
import { motion } from 'framer-motion'
import { 
  ArrowDownTrayIcon, 
  PlayIcon, 
  ChartBarIcon, 
  CloudArrowDownIcon,
  DocumentTextIcon,
  VideoCameraIcon,
  MusicalNoteIcon,
  GlobeAltIcon
} from '@heroicons/react/24/outline'

// Components
import { DownloadForm } from '@/components/DownloadForm'
import { StatsCards } from '@/components/StatsCards'
import { RecentDownloads } from '@/components/RecentDownloads'
import { QuickActions } from '@/components/QuickActions'

export function Dashboard() {
  return (
    <div className="space-y-8">
      {/* Hero Section */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="text-center py-12 px-4"
      >
        <div className="max-w-4xl mx-auto">
          <motion.h1 
            className="text-5xl font-bold text-white mb-6"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.5 }}
          >
            <span className="bg-gradient-to-r from-blue-400 via-purple-500 to-pink-500 bg-clip-text text-transparent">
              YouTube Downloader Pro
            </span>
          </motion.h1>
          
          <motion.p 
            className="text-xl text-gray-300 mb-8 leading-relaxed"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4, duration: 0.5 }}
          >
            World-class YouTube downloader with modern interface, real-time progress tracking,
            and enterprise-grade features. Download videos, playlists, and audio with ease.
          </motion.p>
          
          {/* Feature Highlights */}
          <motion.div 
            className="grid grid-cols-2 md:grid-cols-4 gap-6 mt-12"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6, duration: 0.5 }}
          >
            <div className="flex flex-col items-center p-4 glass rounded-lg">
              <VideoCameraIcon className="w-8 h-8 text-blue-400 mb-2" />
              <span className="text-sm font-medium text-gray-300">8K Quality</span>
            </div>
            <div className="flex flex-col items-center p-4 glass rounded-lg">
              <MusicalNoteIcon className="w-8 h-8 text-green-400 mb-2" />
              <span className="text-sm font-medium text-gray-300">Audio Extract</span>
            </div>
            <div className="flex flex-col items-center p-4 glass rounded-lg">
              <DocumentTextIcon className="w-8 h-8 text-purple-400 mb-2" />
              <span className="text-sm font-medium text-gray-300">Subtitles</span>
            </div>
            <div className="flex flex-col items-center p-4 glass rounded-lg">
              <CloudArrowDownIcon className="w-8 h-8 text-pink-400 mb-2" />
              <span className="text-sm font-medium text-gray-300">Batch Download</span>
            </div>
          </motion.div>
        </div>
      </motion.div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Download Form */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.8, duration: 0.5 }}
          className="mb-8"
        >
          <DownloadForm />
        </motion.div>

        {/* Stats Cards */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 1.0, duration: 0.5 }}
          className="mb-8"
        >
          <StatsCards />
        </motion.div>

        {/* Quick Actions & Recent Downloads */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 1.2, duration: 0.5 }}
            className="lg:col-span-1"
          >
            <QuickActions />
          </motion.div>

          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 1.4, duration: 0.5 }}
            className="lg:col-span-2"
          >
            <RecentDownloads />
          </motion.div>
        </div>

        {/* Footer Information */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 1.6, duration: 0.5 }}
          className="mt-16 py-8 border-t border-gray-700"
        >
          <div className="text-center">
            <p className="text-gray-400 mb-4">
              Built with ❤️ using FastAPI, React, and modern technologies
            </p>
            <div className="flex justify-center space-x-6 text-sm text-gray-500">
              <span>✨ Real-time Progress</span>
              <span>⚡ Concurrent Downloads</span>
              <span>🔒 Secure & Private</span>
              <span>📱 Mobile Optimized</span>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  )
} 