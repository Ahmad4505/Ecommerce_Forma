import {useEffect} from 'react';
import gsap from 'gsap';
import {ScrollTrigger} from 'gsap/ScrollTrigger';
gsap.registerPlugin(ScrollTrigger);
export function useHomepageMotion(){useEffect(()=>{const media=gsap.matchMedia();media.add('(prefers-reduced-motion: no-preference) and (min-width: 768px)',()=>{gsap.to('.hero-photo > img',{yPercent:8,ease:'none',scrollTrigger:{trigger:'.hero',start:'top top',end:'bottom top',scrub:1}});gsap.fromTo('.editorial-image img',{scale:1.08},{scale:1,ease:'none',scrollTrigger:{trigger:'.editorial',start:'top bottom',end:'bottom top',scrub:1}});});return()=>media.revert();},[])}
