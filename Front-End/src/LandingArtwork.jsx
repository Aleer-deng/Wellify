import React from 'react';
import { Footprints, Heart, Leaf, Sparkles, TrendingUp } from 'lucide-react';

export default function LandingArtwork() {
 return <div className="welcome-art">
  <div className="art-orbit orbit-outer" aria-hidden="true"/>
  <div className="art-orbit orbit-inner" aria-hidden="true"/>
  <span className="art-confetti confetti-one" aria-hidden="true">✦</span>
  <span className="art-confetti confetti-two" aria-hidden="true">✧</span>
  <span className="art-confetti confetti-three" aria-hidden="true">✦</span>
  <span className="wellness-bubble bubble-heart" aria-hidden="true"><Heart size={23}/></span>
  <span className="wellness-bubble bubble-leaf" aria-hidden="true"><Leaf size={23}/></span>
  <div className="art-emblem" aria-hidden="true"><Footprints size={64}/></div>
  <h2>Small steps.<br/>Meaningful progress.</h2>
  <div className="art-habit-note"><TrendingUp size={15}/><span>A little better, every day</span><Sparkles size={14}/></div>
  <div className="welcome-metrics"><span><b>Move</b>Your own pace</span><span><b>Earn</b>Verified points</span><span><b>Grow</b>Daily habits</span></div>
 </div>;
}
