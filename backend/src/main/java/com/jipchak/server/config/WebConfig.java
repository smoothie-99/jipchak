package com.jipchak.server.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.ResourceHandlerRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.nio.file.Paths;

@Configuration
public class WebConfig implements WebMvcConfigurer {

    // jipchak.cors.allowed-origins (콤마 구분). 운영에서는 반드시 도메인만 명시.
    @Value("${jipchak.cors.allowed-origins}")
    private String[] allowedOrigins;
    
    @Value("${jipchak.video.base-dir:videos}")
    private String videoBaseDir;

    @Override
    public void addResourceHandlers(ResourceHandlerRegistry registry) {
        String path = Paths.get(videoBaseDir).toAbsolutePath().toUri().toString();

        // http://localhost:8080/jipchak/videos/파일명.mp4 로 접속 가능하게 함
        registry.addResourceHandler("/videos/**")
                .addResourceLocations(path);
    }

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        // allowedOrigins("*") 는 보안상 금지.
        // 와일드카드 패턴(localhost:*) 지원을 위해 allowedOriginPatterns 사용.
        registry.addMapping("/**")
                .allowedOriginPatterns(allowedOrigins)
                .allowedMethods("GET", "POST", "PUT", "DELETE", "OPTIONS")
                .allowedHeaders("*");
    }
}
