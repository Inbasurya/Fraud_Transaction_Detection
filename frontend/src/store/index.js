import { configureStore } from '@reduxjs/toolkit'
import platformReducer from './platformSlice'

export const store = configureStore({
  reducer: {
    platform: platformReducer,
  },
})
