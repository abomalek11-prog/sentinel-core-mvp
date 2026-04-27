'use client';

import { useRef, useMemo } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';

function CPGParticles() {
  const pointsRef = useRef<THREE.Points>(null);
  const linesRef  = useRef<THREE.LineSegments>(null);
  const mouseRef  = useRef({ x: 0, y: 0 });
  const count = 600;
  const threshold = 3.0;

  const { positions, colors, originalPositions } = useMemo(() => {
    const pos = new Float32Array(count * 3);
    const col = new Float32Array(count * 3);
    const orig = new Float32Array(count * 3);
    const teal = new THREE.Color('#1E90B0');
    for (let i = 0; i < count; i++) {
      const r = 10 + Math.random() * 4;
      const theta = Math.random() * Math.PI * 2;
      const phi   = Math.acos(2 * Math.random() - 1);
      const x = r * Math.sin(phi) * Math.cos(theta);
      const y = r * Math.sin(phi) * Math.sin(theta);
      const z = r * Math.cos(phi);
      pos[i * 3]     = x;
      pos[i * 3 + 1] = y;
      pos[i * 3 + 2] = z;
      orig[i * 3]     = x;
      orig[i * 3 + 1] = y;
      orig[i * 3 + 2] = z;
      col[i * 3]     = teal.r;
      col[i * 3 + 1] = teal.g;
      col[i * 3 + 2] = teal.b;
    }
    return { positions: pos, colors: col, originalPositions: orig };
  }, []);

  const linePositions = useMemo(() => new Float32Array(count * count * 0.003 * 6), []);

  const { gl } = useThree();

  useFrame(({ clock, pointer }) => {
    if (!pointsRef.current || !linesRef.current) return;
    const t = clock.getElapsedTime();

    mouseRef.current.x += (pointer.x * 8 - mouseRef.current.x) * 0.05;
    mouseRef.current.y += (pointer.y * 8 - mouseRef.current.y) * 0.05;

    // Rotate
    pointsRef.current.rotation.y = t * 0.03 + mouseRef.current.x * 0.05;
    pointsRef.current.rotation.x = mouseRef.current.y * 0.03;
    linesRef.current.rotation.copy(pointsRef.current.rotation);

    // Pulse some nodes
    const posAttr = pointsRef.current.geometry.attributes.position as THREE.BufferAttribute;
    const colAttr = pointsRef.current.geometry.attributes.color as THREE.BufferAttribute;
    const teal  = new THREE.Color('#1E90B0');
    const amber = new THREE.Color('#FFC44D');

    for (let i = 0; i < count; i++) {
      const pulse = Math.sin(t * 0.5 + i * 0.3) * 0.15;
      posAttr.setXYZ(
        i,
        originalPositions[i * 3] * (1 + pulse * 0.02),
        originalPositions[i * 3 + 1] * (1 + pulse * 0.02),
        originalPositions[i * 3 + 2] * (1 + pulse * 0.02),
      );
      // Occasional amber healing
      const isAmber = Math.sin(t * 0.4 + i * 1.7) > 0.97;
      const c = isAmber ? amber : teal;
      colAttr.setXYZ(i, c.r, c.g, c.b);
    }
    posAttr.needsUpdate = true;
    colAttr.needsUpdate = true;

    // Build edges
    let edgeCount = 0;
    const lineGeo = linesRef.current.geometry;
    const linePos = lineGeo.attributes.position as THREE.BufferAttribute;
    const a = new THREE.Vector3();
    const b = new THREE.Vector3();
    for (let i = 0; i < count && edgeCount < linePositions.length / 6; i += 3) {
      a.set(posAttr.getX(i), posAttr.getY(i), posAttr.getZ(i));
      for (let j = i + 1; j < Math.min(i + 30, count); j += 2) {
        b.set(posAttr.getX(j), posAttr.getY(j), posAttr.getZ(j));
        if (a.distanceTo(b) < threshold) {
          linePos.setXYZ(edgeCount * 2, a.x, a.y, a.z);
          linePos.setXYZ(edgeCount * 2 + 1, b.x, b.y, b.z);
          edgeCount++;
        }
      }
    }
    lineGeo.setDrawRange(0, edgeCount * 2);
    linePos.needsUpdate = true;
  });

  return (
    <>
      <points ref={pointsRef}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[positions, 3]} />
          <bufferAttribute attach="attributes-color" args={[colors, 3]} />
        </bufferGeometry>
        <pointsMaterial size={0.08} vertexColors transparent opacity={0.9} sizeAttenuation />
      </points>
      <lineSegments ref={linesRef}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[linePositions, 3]} />
        </bufferGeometry>
        <lineBasicMaterial color="#0D2A3F" transparent opacity={0.3} />
      </lineSegments>
    </>
  );
}

export function HeroScene() {
  return (
    <div className="absolute inset-0 z-0">
      <Canvas
        camera={{ position: [0, 0, 18], fov: 60 }}
        dpr={[1, 1.5]}
        gl={{ antialias: false, powerPreference: 'high-performance' }}
        style={{ background: 'transparent' }}
      >
        <ambientLight intensity={0.3} color="#0A1828" />
        <pointLight position={[5, 3, 5]} intensity={1} color="#1E90B0" />
        <pointLight position={[-3, -2, 3]} intensity={0.4} color="#FFC44D" />
        <CPGParticles />
      </Canvas>
    </div>
  );
}
