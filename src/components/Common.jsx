import {Component,useEffect,useRef} from 'react';
import gsap from 'gsap';
import {ScrollTrigger} from 'gsap/ScrollTrigger';
gsap.registerPlugin(ScrollTrigger);
export function Reveal({children,className=''}){const ref=useRef();useEffect(()=>{const mm=gsap.matchMedia();mm.add('(prefers-reduced-motion: no-preference)',()=>{gsap.fromTo(Array.from(ref.current.children),{y:24,opacity:0},{y:0,opacity:1,duration:.7,stagger:.08,clearProps:'transform,opacity',scrollTrigger:{trigger:ref.current,start:'top 95%',once:true}});});return()=>mm.revert();},[]);return <div ref={ref} className={className}>{children}</div>}
export class ErrorBoundary extends Component{state={error:false};static getDerivedStateFromError(){return {error:true}}render(){return this.state.error?<div className="empty"><h2>Something needs a fresh start.</h2><button onClick={()=>location.reload()}>Reload Forma</button></div>:this.props.children}}
export function Loading(){return <div className="empty" role="status"><span className="spinner"/> Bringing good things together…</div>}
export function Image({src,alt,...props}){return <img src={src} alt={alt} loading="lazy" onError={e=>{e.currentTarget.onerror=null;e.currentTarget.src='/fallback.svg';}} {...props}/>}
