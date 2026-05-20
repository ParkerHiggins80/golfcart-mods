import { useEffect, useState, useRef } from "react";

export default function Speedometer() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    //parameters
    let speed = 30;
    let maxSpeed = 35;
    let odometer = 12345.6;
    //colors
    let grey1 = '#222222';
    let grey2 = '#616161';
    let green = '#22c55e';
    let yellow = '#ea9f0e';
    let red = '#FF0000';

    //Gradients
    let dialGradient1 = ctx.createLinearGradient(200, 80, 200, 320);
    let dialGradient2 = ctx.createLinearGradient(200, 80, 200, 320);
    //Angles
    const startAngle = 0.75 * Math.PI;
    let endAngle =
      (2.25 * Math.PI - startAngle) * (speed / maxSpeed) + startAngle;
    const twentyAngle = startAngle + (20 / maxSpeed) * (endAngle - startAngle);
    const thirtyAngle = startAngle + (30 / maxSpeed) * (endAngle - startAngle);
    
    //Backround Circle
    ctx.beginPath();
    ctx.arc(200, 200, 151, 0, 2 * Math.PI);
    ctx.fillStyle = "#0d0d0d";
    ctx.fill();

    //Outer Border Arc
    ctx.beginPath();
    ctx.arc(200, 200, 143, startAngle, 2.25 * Math.PI);
    ctx.lineWidth = 1;
    ctx.strokeStyle = grey1;
    ctx.stroke();

    //Grey Background Arc
    ctx.beginPath();
    ctx.lineWidth = 13;
    ctx.strokeStyle = grey1;
    ctx.arc(200, 200, 120, startAngle, 2.25 * Math.PI);
    ctx.stroke();

    //Colored Arc Segments

    
    // Gradient arc 0 to 20
    ctx.beginPath();
    ctx.lineWidth = 13;
    ctx.strokeStyle = green;
    ctx.lineCap = "round";
    ctx.arc(200, 200, 120, startAngle, endAngle);
    ctx.stroke();
    

    // Gradient arc 20 to 30
    if(speed > 20) {
    ctx.beginPath();
    dialGradient1.addColorStop(0, green);
    dialGradient1.addColorStop(.25, yellow);
    dialGradient1.addColorStop(1, yellow);
    ctx.strokeStyle = dialGradient1;
    ctx.arc(200, 200, 120, twentyAngle, endAngle);
    ctx.stroke();
    }
    
    // Red arc 30 to 35
    if(speed > 30) {
    dialGradient2.addColorStop(.2, yellow);
    dialGradient2.addColorStop(.55, yellow);
    dialGradient2.addColorStop(1, red);
    ctx.strokeStyle = dialGradient2;
    ctx.beginPath();
    ctx.arc(200, 200, 120, thirtyAngle, endAngle);
    ctx.stroke();
    }

    //Major Tick Marks & Labels
    for (let i = 0; i <= maxSpeed; i += 5) {
      //Tick mark positions
      const angle =
        (2.25 * Math.PI - 0.75 * Math.PI) * (i / maxSpeed) + 0.75 * Math.PI;
      const innerRadius = 96;
      const outerRadius = 109;
      const x1 = 200 + innerRadius * Math.cos(angle);
      const y1 = 200 + innerRadius * Math.sin(angle);
      const x2 = 200 + outerRadius * Math.cos(angle);
      const y2 = 200 + outerRadius * Math.sin(angle);
      ctx.beginPath();
      ctx.lineWidth = 2;
      ctx.strokeStyle = "#a4a4a4";
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();

      //Speed labels
      const labelRadius = 85;
      const labelX = 200 + labelRadius * Math.cos(angle);
      const labelY = 200 + labelRadius * Math.sin(angle);
      ctx.font = "11px sans-serif";
      ctx.fillStyle = grey2;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(i.toString(), labelX, labelY);
    }

    //Minor Tick Marks
    for (let i = 0; i <= maxSpeed; i += 1) {
      if (i % 5 === 0) continue; // Skip major ticks
      const angle =
        (2.25 * Math.PI - startAngle) * (i / maxSpeed) + startAngle;
      const innerRadius = 103;
      const outerRadius = 109;
      const x1 = 200 + innerRadius * Math.cos(angle);
      const y1 = 200 + innerRadius * Math.sin(angle);
      const x2 = 200 + outerRadius * Math.cos(angle);
      const y2 = 200 + outerRadius * Math.sin(angle);
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.lineWidth = 1;
      ctx.strokeStyle = grey2;
      ctx.stroke();
    }

    //Needle
    const needleLength = 98;
    const needleAngle =
      (2.25 * Math.PI - startAngle) * (speed / maxSpeed) + startAngle;
    const needleX = 200 + needleLength * Math.cos(needleAngle);
    const needleY = 200 + needleLength * Math.sin(needleAngle);
    ctx.beginPath();
    ctx.moveTo(200, 200);
    ctx.lineTo(needleX, needleY);
    ctx.lineWidth = 1;
    ctx.strokeStyle = "#f6f6f6";
    ctx.stroke();

    //Center Circle
    ctx.beginPath();
    ctx.arc(200, 200, 8, 0, 2 * Math.PI);
    ctx.fillStyle = grey1;
    ctx.fill();
    ctx.beginPath();
    ctx.arc(200, 200, 5, 0, 2 * Math.PI);
    ctx.fillStyle = "#f6f6f6";
    ctx.fill();

    //Speed Text
    ctx.font = "12px sans-serif";
    ctx.fillStyle = grey2;
    ctx.fillText("mph", 200, 277);
    ctx.font = "50px sans-serif";
    ctx.fillStyle = "#ffffff";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(`${speed}`, 200, 250);
    ctx.font = "10px sans-serif";
    ctx.textAlign = "center";
    ctx.fillStyle = "#252525";
    ctx.fillText(`${odometer.toFixed(1)} mi`, 200, 293);

  }, []);

  return <canvas ref={canvasRef} width={400} height={400} />;
}
