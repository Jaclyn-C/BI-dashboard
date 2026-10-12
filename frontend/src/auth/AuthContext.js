import { createContext } from 'react'

// 会话上下文：AuthProvider 提供，useAuth 消费（分文件避免 react-refresh 告警）
const AuthContext = createContext(null)

export default AuthContext
