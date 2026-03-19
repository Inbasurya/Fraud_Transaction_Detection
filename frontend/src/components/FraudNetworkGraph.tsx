import React, { useEffect, useRef } from "react";
import * as d3 from "d3";
import type { NetworkData, GraphNode, GraphEdge } from "../types";

interface Props {
  data: NetworkData | null;
}

const typeColors: Record<string, string> = {
  customer: "#3b82f6",
  merchant: "#10b981",
  device: "#f59e0b",
  ip: "#8b5cf6",
};

export default function FraudNetworkGraph({ data }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!data || !svgRef.current) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const width = svgRef.current.clientWidth;
    const height = 500;

    svg.attr("viewBox", `0 0 ${width} ${height}`);

    const nodes: (GraphNode & d3.SimulationNodeDatum)[] = data.nodes.map((n) => ({
      ...n,
    }));
    const links: { source: string; target: string; relation: string }[] =
      data.edges.map((e) => ({ ...e }));

    const simulation = d3
      .forceSimulation(nodes as d3.SimulationNodeDatum[])
      .force(
        "link",
        d3
          .forceLink(links)
          .id((d: any) => d.id)
          .distance(80)
      )
      .force("charge", d3.forceManyBody().strength(-100))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide().radius(20));

    const g = svg.append("g");

    // Zoom
    svg.call(
      d3.zoom<SVGSVGElement, unknown>().scaleExtent([0.3, 4]).on("zoom", (event) => {
        g.attr("transform", event.transform);
      })
    );

    // Links
    const link = g
      .append("g")
      .selectAll("line")
      .data(links)
      .join("line")
      .attr("stroke", "#374151")
      .attr("stroke-width", 1)
      .attr("stroke-opacity", 0.6);

    // Nodes
    const node = g
      .append("g")
      .selectAll("circle")
      .data(nodes)
      .join("circle")
      .attr("r", (d) => (d.fraud_score > 0.5 ? 8 : 5))
      .attr("fill", (d) => typeColors[d.type] || "#6b7280")
      .attr("stroke", (d) => (d.fraud_score > 0.5 ? "#ef4444" : "none"))
      .attr("stroke-width", (d) => (d.fraud_score > 0.5 ? 2 : 0))
      .call(
        d3
          .drag<SVGCircleElement, GraphNode & d3.SimulationNodeDatum>()
          .on("start", (event, d) => {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on("drag", (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on("end", (event, d) => {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          })
      );

    // Tooltip
    node.append("title").text((d) => `${d.id} (${d.type})`);

    simulation.on("tick", () => {
      link
        .attr("x1", (d: any) => d.source.x)
        .attr("y1", (d: any) => d.source.y)
        .attr("x2", (d: any) => d.target.x)
        .attr("y2", (d: any) => d.target.y);

      node.attr("cx", (d: any) => d.x).attr("cy", (d: any) => d.y);
    });

    return () => {
      simulation.stop();
    };
  }, [data]);

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-300">Fraud Network Graph</h3>
        <div className="flex gap-3 text-xs">
          {Object.entries(typeColors).map(([type, color]) => (
            <span key={type} className="flex items-center gap-1">
              <span
                className="w-2.5 h-2.5 rounded-full inline-block"
                style={{ backgroundColor: color }}
              />
              {type}
            </span>
          ))}
        </div>
      </div>
      <svg ref={svgRef} className="w-full" style={{ height: 500 }} />
    </div>
  );
}
