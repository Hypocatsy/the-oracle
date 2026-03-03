import oracleLogo from '../assets/oracle-logo.png'
import '../styles/Header.css'

export default function Header() {
  return (
    <header className="header">
      <img src={oracleLogo} alt="The Oracle" className="header-logo" />
    </header>
  )
}
