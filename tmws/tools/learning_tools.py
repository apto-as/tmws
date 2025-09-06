"""
Learning and Pattern Recognition Tools for TMWS MCP Server
Handles pattern learning, application, and knowledge evolution
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from fastmcp import FastMCP

from .base_tool import BaseTool


class PatternLearnRequest(BaseModel):
    """Pattern learning parameters."""
    pattern_name: str = Field(..., description="Pattern name/identifier")
    pattern_content: str = Field(..., description="Pattern content and description")
    category: str = Field(..., description="Pattern category")
    examples: List[str] = Field(default_factory=list, description="Usage examples")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0, description="Pattern confidence score")


class PatternApplicationRequest(BaseModel):
    """Pattern application parameters."""
    pattern_query: str = Field(..., description="Query to find applicable patterns")
    context: str = Field(..., description="Application context")
    max_patterns: int = Field(default=5, ge=1, le=20, description="Maximum patterns to return")
    min_similarity: float = Field(default=0.7, ge=0.0, le=1.0, description="Minimum similarity threshold")


class LearningTools(BaseTool):
    """Learning and pattern recognition tools for TMWS MCP server."""

    async def register_tools(self, mcp: FastMCP) -> None:
        """Register learning tools with FastMCP instance."""

        @mcp.tool()
        async def learn_pattern(
            pattern_name: str,
            pattern_content: str,
            category: str,
            examples: List[str] = None,
            metadata: Dict[str, Any] = None,
            confidence: float = 0.8
        ) -> Dict[str, Any]:
            """
            Learn and store a new pattern for future application.
            
            Patterns represent reusable solutions, optimizations, or knowledge
            that can be applied to similar situations in the future.
            
            Args:
                pattern_name: Unique identifier for the pattern
                pattern_content: Detailed description of the pattern
                category: Pattern category (optimization, architecture, security, etc.)
                examples: List of usage examples
                metadata: Additional structured metadata
                confidence: Confidence score for pattern reliability
                
            Returns:
                Dict containing pattern storage confirmation and details
            """
            request = PatternLearnRequest(
                pattern_name=pattern_name,
                pattern_content=pattern_content,
                category=category,
                examples=examples or [],
                metadata=metadata or {},
                confidence=confidence
            )
            
            async def _learn_pattern(session, services):
                memory_service = services['memory_service']
                vectorization_service = services['vectorization_service']
                
                # Create comprehensive pattern data
                pattern_data = {
                    "pattern_name": request.pattern_name,
                    "pattern_content": request.pattern_content,
                    "category": request.category,
                    "examples": request.examples,
                    "confidence": request.confidence,
                    "learned_at": datetime.utcnow().isoformat(),
                    "application_count": 0,
                    "success_rate": 1.0,
                    **request.metadata
                }
                
                # Create searchable content for vectorization
                searchable_content = f"""
                PATTERN: {request.pattern_name}
                CATEGORY: {request.category}
                DESCRIPTION: {request.pattern_content}
                EXAMPLES: {' | '.join(request.examples)}
                """
                
                # Generate vector embedding
                embedding = await vectorization_service.vectorize_text(searchable_content.strip())
                
                # Store as high-importance memory
                memory = await memory_service.create_memory(
                    content=searchable_content.strip(),
                    memory_type="pattern",
                    tags=["pattern", request.category, request.pattern_name, "learning"],
                    metadata=pattern_data,
                    embedding=embedding.tolist(),
                    importance=0.9  # Patterns are high importance
                )
                
                return {
                    "pattern_id": str(memory.id),
                    "pattern_name": request.pattern_name,
                    "category": request.category,
                    "confidence": request.confidence,
                    "examples_count": len(request.examples),
                    "vector_dimensions": len(embedding),
                    "stored_at": memory.created_at.isoformat()
                }
            
            result = await self.execute_with_session(_learn_pattern)
            return self.format_success(result, f"Pattern '{pattern_name}' learned successfully")

        @mcp.tool()
        async def apply_pattern(
            pattern_query: str,
            context: str,
            max_patterns: int = 5,
            min_similarity: float = 0.7
        ) -> Dict[str, Any]:
            """
            Find and apply relevant patterns to a given context.
            
            Searches for patterns matching the query and context, returning
            applicable patterns with application guidance.
            
            Args:
                pattern_query: Query describing the pattern need
                context: Specific context for pattern application
                max_patterns: Maximum number of patterns to return
                min_similarity: Minimum similarity threshold
                
            Returns:
                Dict containing applicable patterns and application guidance
            """
            request = PatternApplicationRequest(
                pattern_query=pattern_query,
                context=context,
                max_patterns=max_patterns,
                min_similarity=min_similarity
            )
            
            async def _apply_pattern(session, services):
                memory_service = services['memory_service']
                vectorization_service = services['vectorization_service']
                
                # Create search query combining pattern query and context
                search_query = f"PATTERN SEARCH: {request.pattern_query} CONTEXT: {request.context}"
                
                # Generate query embedding
                query_embedding = await vectorization_service.vectorize_text(search_query)
                
                # Search for relevant patterns
                patterns = await memory_service.search_similar_memories(
                    embedding=query_embedding.tolist(),
                    memory_type="pattern",
                    limit=request.max_patterns,
                    min_similarity=request.min_similarity
                )
                
                if not patterns:
                    return {
                        "found": False,
                        "query": request.pattern_query,
                        "context": request.context,
                        "message": "No matching patterns found",
                        "suggestion": "Consider learning new patterns for this scenario"
                    }
                
                # Process and rank patterns
                applicable_patterns = []
                for pattern in patterns:
                    pattern_data = pattern.metadata_json or {}
                    
                    # Update application statistics
                    pattern_data["application_count"] = pattern_data.get("application_count", 0) + 1
                    pattern_data["last_applied"] = datetime.utcnow().isoformat()
                    
                    # Update memory with new statistics
                    await memory_service.update_memory(
                        str(pattern.id),
                        {"metadata": pattern_data}
                    )
                    
                    applicable_patterns.append({
                        "pattern_id": str(pattern.id),
                        "pattern_name": pattern_data.get("pattern_name", "Unknown"),
                        "category": pattern_data.get("category", "general"),
                        "pattern_content": pattern_data.get("pattern_content", ""),
                        "confidence": pattern_data.get("confidence", 0.5),
                        "similarity": getattr(pattern, 'similarity', 0.0),
                        "application_count": pattern_data.get("application_count", 0),
                        "success_rate": pattern_data.get("success_rate", 1.0),
                        "examples": pattern_data.get("examples", []),
                        "metadata": {k: v for k, v in pattern_data.items() 
                                  if k not in ["pattern_name", "category", "pattern_content", "examples"]}
                    })
                
                # Sort by combination of similarity and confidence
                applicable_patterns.sort(
                    key=lambda p: (p["similarity"] * 0.6 + p["confidence"] * 0.4),
                    reverse=True
                )
                
                return {
                    "found": True,
                    "query": request.pattern_query,
                    "context": request.context,
                    "pattern_count": len(applicable_patterns),
                    "patterns": applicable_patterns,
                    "application_guidance": {
                        "recommended_pattern": applicable_patterns[0] if applicable_patterns else None,
                        "confidence_threshold": min_similarity,
                        "application_notes": f"Found {len(applicable_patterns)} applicable patterns"
                    }
                }
            
            result = await self.execute_with_session(_apply_pattern)
            return self.format_success(result, f"Found {result.get('pattern_count', 0)} applicable patterns")

        @mcp.tool()
        async def get_pattern_analytics() -> Dict[str, Any]:
            """
            Get analytics on learned patterns and their usage.
            
            Provides insights into pattern learning effectiveness, usage patterns,
            and knowledge base evolution.
            
            Returns:
                Dict containing comprehensive pattern analytics
            """
            async def _get_pattern_analytics(session, services):
                memory_service = services['memory_service']
                
                # Get all pattern memories
                patterns = await memory_service.search_memories(
                    query="",
                    memory_type="pattern",
                    limit=1000  # Get all patterns
                )
                
                if not patterns:
                    return {
                        "total_patterns": 0,
                        "message": "No patterns learned yet"
                    }
                
                # Analyze patterns
                category_distribution = {}
                confidence_distribution = {"high": 0, "medium": 0, "low": 0}
                application_stats = []
                success_rates = []
                learning_timeline = {}
                
                for pattern in patterns:
                    metadata = pattern.metadata_json or {}
                    
                    # Category distribution
                    category = metadata.get("category", "unknown")
                    category_distribution[category] = category_distribution.get(category, 0) + 1
                    
                    # Confidence distribution
                    confidence = metadata.get("confidence", 0.5)
                    if confidence >= 0.8:
                        confidence_distribution["high"] += 1
                    elif confidence >= 0.6:
                        confidence_distribution["medium"] += 1
                    else:
                        confidence_distribution["low"] += 1
                    
                    # Application statistics
                    app_count = metadata.get("application_count", 0)
                    application_stats.append(app_count)
                    
                    # Success rates
                    success_rate = metadata.get("success_rate", 1.0)
                    success_rates.append(success_rate)
                    
                    # Learning timeline
                    learned_date = metadata.get("learned_at")
                    if learned_date:
                        try:
                            date_key = datetime.fromisoformat(learned_date).date().isoformat()
                            learning_timeline[date_key] = learning_timeline.get(date_key, 0) + 1
                        except (ValueError, TypeError):
                            pass
                
                # Calculate statistics
                total_applications = sum(application_stats)
                avg_applications = total_applications / len(patterns) if patterns else 0
                avg_success_rate = sum(success_rates) / len(success_rates) if success_rates else 0
                
                # Find most/least used patterns
                patterns_with_usage = [
                    {
                        "pattern_name": p.metadata_json.get("pattern_name", "Unknown"),
                        "category": p.metadata_json.get("category", "unknown"),
                        "application_count": p.metadata_json.get("application_count", 0),
                        "success_rate": p.metadata_json.get("success_rate", 1.0),
                        "confidence": p.metadata_json.get("confidence", 0.5)
                    }
                    for p in patterns
                ]
                
                most_used = sorted(patterns_with_usage, key=lambda x: x["application_count"], reverse=True)[:5]
                least_used = sorted(patterns_with_usage, key=lambda x: x["application_count"])[:5]
                
                return {
                    "overview": {
                        "total_patterns": len(patterns),
                        "total_applications": total_applications,
                        "avg_applications_per_pattern": round(avg_applications, 2),
                        "avg_success_rate": round(avg_success_rate, 3),
                        "knowledge_base_health": "excellent" if avg_success_rate > 0.9 else "good" if avg_success_rate > 0.7 else "needs_improvement"
                    },
                    "distribution": {
                        "by_category": category_distribution,
                        "by_confidence": confidence_distribution
                    },
                    "usage_patterns": {
                        "most_applied": most_used,
                        "least_applied": least_used,
                        "unused_patterns": len([p for p in patterns_with_usage if p["application_count"] == 0])
                    },
                    "learning_timeline": dict(sorted(learning_timeline.items())),
                    "recommendations": {
                        "high_value_patterns": len([p for p in patterns_with_usage if p["application_count"] > avg_applications and p["success_rate"] > 0.8]),
                        "patterns_to_review": len([p for p in patterns_with_usage if p["success_rate"] < 0.6]),
                        "knowledge_gaps": [cat for cat, count in category_distribution.items() if count < 3]
                    },
                    "generated_at": datetime.utcnow().isoformat()
                }
            
            result = await self.execute_with_session(_get_pattern_analytics)
            return self.format_success(result, "Pattern analytics generated")

        @mcp.tool()
        async def evolve_pattern(
            pattern_id: str,
            evolution_data: Dict[str, Any],
            success_feedback: bool,
            notes: Optional[str] = None
        ) -> Dict[str, Any]:
            """
            Evolve an existing pattern based on usage feedback.
            
            Updates patterns based on application results, improving accuracy
            and effectiveness over time.
            
            Args:
                pattern_id: ID of pattern to evolve
                evolution_data: Data about pattern evolution/improvement
                success_feedback: Whether recent application was successful
                notes: Optional evolution notes
                
            Returns:
                Dict containing pattern evolution results
            """
            async def _evolve_pattern(session, services):
                memory_service = services['memory_service']
                
                # Get current pattern
                current_memory = await memory_service.get_memory(pattern_id)
                if not current_memory:
                    raise ValueError(f"Pattern {pattern_id} not found")
                
                current_metadata = current_memory.metadata_json or {}
                
                # Calculate new success rate
                current_applications = current_metadata.get("application_count", 1)
                current_success_rate = current_metadata.get("success_rate", 1.0)
                
                # Update success rate with new feedback
                if success_feedback:
                    new_success_rate = ((current_success_rate * (current_applications - 1)) + 1.0) / current_applications
                else:
                    new_success_rate = ((current_success_rate * (current_applications - 1)) + 0.0) / current_applications
                
                # Update pattern metadata
                evolved_metadata = {
                    **current_metadata,
                    "success_rate": new_success_rate,
                    "last_evolved": datetime.utcnow().isoformat(),
                    "evolution_count": current_metadata.get("evolution_count", 0) + 1,
                    "evolution_notes": notes,
                    **evolution_data
                }
                
                # Update confidence based on success rate and application count
                if current_applications > 5:  # Only adjust confidence after sufficient data
                    if new_success_rate > 0.9:
                        evolved_metadata["confidence"] = min(1.0, evolved_metadata.get("confidence", 0.8) + 0.1)
                    elif new_success_rate < 0.6:
                        evolved_metadata["confidence"] = max(0.1, evolved_metadata.get("confidence", 0.8) - 0.1)
                
                # Update the pattern memory
                updated_memory = await memory_service.update_memory(
                    pattern_id,
                    {"metadata": evolved_metadata}
                )
                
                return {
                    "pattern_id": pattern_id,
                    "pattern_name": evolved_metadata.get("pattern_name", "Unknown"),
                    "evolution_summary": {
                        "previous_success_rate": current_success_rate,
                        "new_success_rate": new_success_rate,
                        "previous_confidence": current_metadata.get("confidence", 0.8),
                        "new_confidence": evolved_metadata.get("confidence", 0.8),
                        "evolution_count": evolved_metadata["evolution_count"],
                        "applications_analyzed": current_applications
                    },
                    "evolution_data": evolution_data,
                    "success_feedback": success_feedback,
                    "notes": notes,
                    "evolved_at": evolved_metadata["last_evolved"]
                }
            
            result = await self.execute_with_session(_evolve_pattern)
            return self.format_success(result, f"Pattern evolved - Success rate: {result.get('evolution_summary', {}).get('new_success_rate', 0):.2f}")

        @mcp.tool()
        async def suggest_learning_opportunities() -> Dict[str, Any]:
            """
            Suggest new learning opportunities based on system usage patterns.
            
            Analyzes current knowledge gaps and usage patterns to recommend
            new patterns or knowledge areas to explore.
            
            Returns:
                Dict containing learning opportunity recommendations
            """
            async def _suggest_opportunities(session, services):
                memory_service = services['memory_service']
                
                # Analyze current knowledge base
                all_memories = await memory_service.get_recent_memories(limit=1000)
                pattern_memories = await memory_service.search_memories(
                    query="",
                    memory_type="pattern",
                    limit=1000
                )
                
                # Analyze memory types and topics
                memory_types = {}
                common_tags = {}
                
                for memory in all_memories:
                    memory_type = memory.memory_type
                    memory_types[memory_type] = memory_types.get(memory_type, 0) + 1
                    
                    for tag in memory.tags:
                        common_tags[tag] = common_tags.get(tag, 0) + 1
                
                # Analyze pattern categories
                pattern_categories = {}
                for pattern in pattern_memories:
                    metadata = pattern.metadata_json or {}
                    category = metadata.get("category", "unknown")
                    pattern_categories[category] = pattern_categories.get(category, 0) + 1
                
                # Generate learning suggestions
                suggestions = []
                
                # Suggest patterns for high-frequency, low-pattern topics
                high_activity_areas = sorted(memory_types.items(), key=lambda x: x[1], reverse=True)[:10]
                for memory_type, count in high_activity_areas:
                    pattern_count = pattern_categories.get(memory_type, 0)
                    if count > 10 and pattern_count < 3:  # High activity, low pattern coverage
                        suggestions.append({
                            "type": "pattern_opportunity",
                            "area": memory_type,
                            "priority": "high",
                            "reason": f"High activity ({count} memories) but low pattern coverage ({pattern_count} patterns)",
                            "suggested_action": f"Learn patterns for {memory_type} operations"
                        })
                
                # Suggest knowledge consolidation for scattered topics
                frequent_tags = {tag: count for tag, count in common_tags.items() if count > 5}
                for tag, count in frequent_tags.items():
                    if tag not in ["pattern", "learning"]:  # Skip meta tags
                        suggestions.append({
                            "type": "consolidation_opportunity",
                            "area": tag,
                            "priority": "medium",
                            "reason": f"Frequent topic ({count} occurrences) could benefit from knowledge consolidation",
                            "suggested_action": f"Create comprehensive patterns or documentation for {tag}"
                        })
                
                # Suggest pattern improvement for low-success patterns
                low_success_patterns = []
                for pattern in pattern_memories:
                    metadata = pattern.metadata_json or {}
                    success_rate = metadata.get("success_rate", 1.0)
                    application_count = metadata.get("application_count", 0)
                    
                    if application_count > 3 and success_rate < 0.7:
                        low_success_patterns.append({
                            "pattern_name": metadata.get("pattern_name", "Unknown"),
                            "success_rate": success_rate,
                            "applications": application_count
                        })
                
                if low_success_patterns:
                    suggestions.append({
                        "type": "improvement_opportunity",
                        "area": "pattern_optimization",
                        "priority": "high",
                        "reason": f"{len(low_success_patterns)} patterns have low success rates",
                        "suggested_action": "Review and improve low-performing patterns",
                        "details": low_success_patterns
                    })
                
                # Suggest new learning areas based on trends
                recent_memories = await memory_service.get_recent_memories(limit=100)
                recent_trends = {}
                for memory in recent_memories:
                    for tag in memory.tags:
                        recent_trends[tag] = recent_trends.get(tag, 0) + 1
                
                emerging_topics = {
                    tag: count for tag, count in recent_trends.items() 
                    if count > 3 and tag not in pattern_categories
                }
                
                for topic, count in emerging_topics.items():
                    suggestions.append({
                        "type": "emerging_opportunity",
                        "area": topic,
                        "priority": "medium",
                        "reason": f"Emerging topic in recent activity ({count} recent mentions)",
                        "suggested_action": f"Explore and learn patterns for {topic}"
                    })
                
                # Sort suggestions by priority
                priority_order = {"high": 3, "medium": 2, "low": 1}
                suggestions.sort(key=lambda x: priority_order.get(x["priority"], 0), reverse=True)
                
                return {
                    "knowledge_base_summary": {
                        "total_memories": len(all_memories),
                        "total_patterns": len(pattern_memories),
                        "memory_types": len(memory_types),
                        "pattern_categories": len(pattern_categories),
                        "coverage_ratio": len(pattern_categories) / len(memory_types) if memory_types else 0
                    },
                    "learning_opportunities": suggestions[:10],  # Top 10 suggestions
                    "opportunity_count": len(suggestions),
                    "priority_breakdown": {
                        priority: len([s for s in suggestions if s["priority"] == priority])
                        for priority in ["high", "medium", "low"]
                    },
                    "generated_at": datetime.utcnow().isoformat()
                }
            
            result = await self.execute_with_session(_suggest_opportunities)
            return self.format_success(result, f"Generated {result.get('opportunity_count', 0)} learning opportunities")