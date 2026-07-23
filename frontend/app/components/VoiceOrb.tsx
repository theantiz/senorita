"use client";

import React, { useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Sphere, MeshDistortMaterial } from '@react-three/drei';
import * as THREE from 'three';

function SiriLights() {
  const groupRef = useRef<THREE.Group>(null);
  
  useFrame((state) => {
    if (groupRef.current) {
      groupRef.current.rotation.y = state.clock.elapsedTime * 0.5;
      groupRef.current.rotation.z = state.clock.elapsedTime * 0.3;
    }
  });

  return (
    <group ref={groupRef}>
      <pointLight position={[2, 0, 0]} color="#ffffff" intensity={3} distance={5} />
      <pointLight position={[-2, 0, 0]} color="#f0f0f0" intensity={3} distance={5} />
      <pointLight position={[0, 2, 0]} color="#ffffff" intensity={3} distance={5} />
      <pointLight position={[0, -2, 0]} color="#e0e0e0" intensity={3} distance={5} />
    </group>
  );
}

function OrbMesh({ getFrequencies }: { getFrequencies: () => Uint8Array | null }) {
  const meshRef = useRef<THREE.Mesh>(null);
  const materialRef = useRef<any>(null);

  // Base color is white
  const awakeColor = useMemo(() => new THREE.Color('#ffffff'), []);

  useFrame((state) => {
    if (!meshRef.current || !materialRef.current) return;

    const freqs = getFrequencies();
    
    // Calculate average volume/frequency
    let avgFreq = 0;
    if (freqs) {
      let sum = 0;
      for (let i = 0; i < 32; i++) {
        sum += freqs[i];
      }
      avgFreq = sum / 32;
    }

    // Map 0-255 frequency to a reasonable scale
    const scale = 1 + (avgFreq / 255) * 0.4;
    meshRef.current.scale.lerp(new THREE.Vector3(scale, scale, scale), 0.1);

    // Distort the mesh based on audio
    const distortion = 0.6 + (avgFreq / 255) * 0.8;
    materialRef.current.distort = THREE.MathUtils.lerp(materialRef.current.distort, distortion, 0.1);
    
    // Rotate slowly
    meshRef.current.rotation.x = state.clock.elapsedTime * 0.2;
    meshRef.current.rotation.y = state.clock.elapsedTime * 0.3;
    
    materialRef.current.color.lerp(awakeColor, 0.1);
  });

  return (
    <Sphere ref={meshRef} args={[1, 64, 64]}>
      <MeshDistortMaterial
        ref={materialRef}
        color="#ffffff"
        emissive="#ffffff"
        emissiveIntensity={0.6}
        envMapIntensity={0.8}
        clearcoat={1}
        clearcoatRoughness={0}
        metalness={0.4}
        roughness={0.1}
        distort={0.4}
        speed={5}
      />
    </Sphere>
  );
}

export function VoiceOrb({ getFrequencies, onClick }: { getFrequencies: () => Uint8Array | null, onClick?: () => void }) {
  return (
    <div 
      className="relative w-full h-full flex flex-col items-center justify-center cursor-pointer transition-transform hover:scale-105 active:scale-95"
      onClick={onClick}
    >
      <div className="w-full h-40 md:h-64 pointer-events-none">
        <Canvas camera={{ position: [0, 0, 3], fov: 45 }}>
          <ambientLight intensity={0.2} />
          <SiriLights />
          <OrbMesh getFrequencies={getFrequencies} />
        </Canvas>
      </div>
    </div>
  );
}

