import logo from './wellify-logo.png';
import './brand-logo.css';

export default function BrandLogo() {
  return <span className="brand-logo"><img src={logo} alt="Wellify" /><img className="brand-logo-wordmark" src={logo} alt="" aria-hidden="true" /></span>;
}
